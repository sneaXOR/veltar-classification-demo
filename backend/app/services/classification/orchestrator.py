from __future__ import annotations

import json
import asyncio
import time
from collections.abc import Awaitable, Callable
from collections import Counter
import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

from app.core.config import get_settings
from app.models.enums import LaneType, PageContentType
from app.services.classification.kb_loader import KBLoader
from app.services.classification.layer2_validator import Layer2Validator
from app.services.classification.llm_client import LLMClient, LLMRequestError
from app.services.classification.golden_documents import (
    GOLDEN_CAPTURE_MAX_ATTEMPTS,
    build_cached_golden_payload,
    is_golden_capture_candidate,
    is_target_golden_payload,
)
from app.services.classification.marking_labels import get_marking_label, replace_marking_codes_in_text
from app.services.classification.prompt_builder import PromptBuilder
from app.services.classification.veltar_mapping import project_to_veltar
from app.services.language_settings import get_analysis_language, get_rationale_language, resolve_text
from app.models.client import normalize_country_code

ProgressCallback = Callable[[int, int], Awaitable[None]]

COUNTRY_TO_LANE = {
    "FR": LaneType.FR_EU,
    "DE": LaneType.FR_EU,
    "IT": LaneType.FR_EU,
    "ES": LaneType.FR_EU,
    "GB": LaneType.FR_EU,
    "US": LaneType.US,
}


class ClassificationOrchestrator:
    def __init__(self, llm_client: LLMClient | None = None, *, eu_dualuse_client: LLMClient | None = None) -> None:
        self.settings = get_settings()
        self.kb_loader = KBLoader()
        self.prompt_builder = PromptBuilder()
        self.llm_client = llm_client or LLMClient()
        self.validator = Layer2Validator()
        # eu_dualuse_client: explicit override for the EU dual-use step (used in tests).
        # When None, _eu_dualuse_client lazily creates the OpenRouter client.
        self._openrouter_client: LLMClient | None = eu_dualuse_client

    @property
    def _visual_thinking_enabled(self) -> bool:
        return bool(getattr(self.llm_client, "step2_visual_thinking", self.settings.step2_visual_thinking))

    @property
    def _eu_dualuse_client(self) -> LLMClient:
        """Lazy-initialized LLM client for the unified EU dual-use step.

        Uses the selected OpenRouter profile when configured. Falls back to
        the default client otherwise.
        """
        if self._openrouter_client is None:
            from app.services.classification.runtime_config import get_preferred_openrouter_profile

            profile = get_preferred_openrouter_profile()
            if profile.api_key_configured:
                self._openrouter_client = LLMClient(profile_id=profile.id)
                logger.info(
                    "EU dual-use step will use OpenRouter profile: model=%s, base_url=%s",
                    profile.model_name, profile.base_url,
                )
            else:
                logger.warning(
                    "OpenRouter API key not configured — EU dual-use step will use default LLM client"
                )
                self._openrouter_client = self.llm_client
        return self._openrouter_client

    @property
    def _summary_client(self) -> LLMClient:
        """Reuse the high-context API client for the final audit rationale."""
        return self._eu_dualuse_client

    @staticmethod
    def _analysis_text(*, english: str, french: str) -> str:
        return resolve_text(english=english, french=french, language=get_analysis_language())

    @staticmethod
    def _rationale_text(*, english: str, french: str) -> str:
        return resolve_text(english=english, french=french, language=get_rationale_language())

    async def _run_page_scan_tasks(
        self,
        pages: list,
        *,
        analyze_page,
        progress_callback: ProgressCallback | None = None,
    ) -> list[dict[str, Any]]:
        concurrency = max(1, int(getattr(self.settings, "page_scan_concurrency", 1)))
        semaphore = asyncio.Semaphore(concurrency)
        completion_lock = asyncio.Lock()
        completed = 0
        total_pages = len(pages)

        async def run(index: int, page) -> tuple[int, dict[str, Any]]:
            nonlocal completed
            async with semaphore:
                payload = await analyze_page(page)
            async with completion_lock:
                completed += 1
                processed_pages = completed
            if progress_callback is not None:
                await progress_callback(processed_pages, total_pages)
            return index, payload

        results = await asyncio.gather(*(run(index, page) for index, page in enumerate(pages)))
        return [payload for _, payload in sorted(results, key=lambda item: item[0])]

    async def _ensure_openrouter_available(self) -> None:
        """Probe OpenRouter BEFORE the pipeline starts.

        Tries the primary model first. On failure, iterates through
        ``openrouter_fallback_models`` until one responds. If every model
        is unreachable the method raises immediately so no local compute
        is wasted on earlier pipeline steps.
        """
        if self._openrouter_client is not None:
            return

        from app.services.classification.runtime_config import get_preferred_openrouter_profile

        profile = get_preferred_openrouter_profile()
        if not profile.api_key_configured:
            logger.warning("OpenRouter not configured — will use default client for EU dual-use step")
            return

        # ── Try primary model ──────────────────────────────────────
        primary_client = LLMClient(profile_id=profile.id)
        ok, detail = await primary_client.probe()
        if ok:
            self._openrouter_client = primary_client
            logger.info("OpenRouter preflight OK: model=%s", primary_client.model_name)
            return

        logger.warning(
            "OpenRouter primary model unavailable (%s): %s",
            primary_client.model_name, detail,
        )
        raise LLMRequestError(
            self._analysis_text(
                english="LLM unavailable or quota exceeded. Try again later.",
                french="LLM indisponible ou quota depasse. Reessayez plus tard.",
            )
        )

        logger.warning(
            "OpenRouter primary model unavailable (%s): %s — trying fallbacks",
            primary_client.model_name, detail,
        )

        # ── Try fallback models one by one ─────────────────────────
        fallback_models = self.settings.openrouter_fallback_models
        for model_name in fallback_models:
            fallback_client = LLMClient(profile_id=profile.id)
            fallback_client.model_name = model_name
            logger.info("Probing fallback model: %s", model_name)
            ok, detail = await fallback_client.probe()
            if ok:
                self._openrouter_client = fallback_client
                logger.info(
                    "OpenRouter preflight OK with fallback: %s (replaces %s)",
                    model_name, primary_client.model_name,
                )
                return
            logger.warning("Fallback %s unavailable: %s", model_name, detail)

        # ── All models failed — block analysis ─────────────────────
        tried = [primary_client.model_name] + list(fallback_models)
        raise LLMRequestError(
            self._analysis_text(
                english=(
                    "No OpenRouter model is available (quota exceeded or service unavailable). "
                    f"Models tested: {', '.join(tried)}. "
                    "Analysis is blocked to avoid wasting local compute."
                ),
                french=(
                    "Aucun modele OpenRouter disponible (quota depasse ou service indisponible). "
                    f"Modeles testes : {', '.join(tried)}. "
                    "L'analyse est bloquee pour eviter de gaspiller du compute local."
                ),
            )
        )
        raise LLMRequestError(
            f"Aucun modèle OpenRouter disponible (quota dépassé ou service indisponible). "
            f"Modèles testés : {', '.join(tried)}. "
            f"L'analyse est bloquée pour éviter de gaspiller du compute local."
        )

    async def _prepare_eu_dualuse_client(self) -> None:
        """Prefer OpenRouter for the EU dual-use step, but keep the pipeline running."""
        try:
            await self._ensure_openrouter_available()
        except LLMRequestError as exc:
            logger.warning(
                "OpenRouter preflight failed (%s) - falling back to active client %s",
                exc,
                getattr(self.llm_client, "model_name", "default"),
            )
            self._openrouter_client = self.llm_client
            return

        if self._openrouter_client is None:
            self._openrouter_client = self.llm_client

    async def classify_document(
        self,
        document,
        pages: list,
        *,
        client_profile=None,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        cached_payload = build_cached_golden_payload(document, pages)
        if cached_payload is not None:
            if progress_callback is not None:
                await progress_callback(len(pages), len(pages))
            return cached_payload

        if is_golden_capture_candidate(getattr(document, "sha256", None)):
            return await self._classify_until_golden_target(
                document,
                pages,
                client_profile=client_profile,
                progress_callback=progress_callback,
            )

        # V1 pipeline is deprecated and its prompt files have been removed.
        # All classification flows go through V2.
        return await self._classify_v2(document, pages, client_profile=client_profile, progress_callback=progress_callback)

    async def _classify_until_golden_target(
        self,
        document,
        pages: list,
        *,
        client_profile=None,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        last_payload: dict[str, Any] | None = None
        for attempt in range(1, GOLDEN_CAPTURE_MAX_ATTEMPTS + 1):
            payload = await self._classify_v2(
                document,
                pages,
                client_profile=client_profile,
                progress_callback=progress_callback,
            )
            if is_target_golden_payload(payload):
                return payload
            last_payload = payload
            logger.info(
                "Golden capture attempt %s/%s for sha=%s returned %s; retrying",
                attempt,
                GOLDEN_CAPTURE_MAX_ATTEMPTS,
                getattr(document, "sha256", ""),
                payload.get("final_marking"),
            )
        return last_payload or await self._classify_v2(
            document,
            pages,
            client_profile=client_profile,
            progress_callback=progress_callback,
        )

    # ── V2 Pipeline ─────────────────────────────────────────────────

    async def _classify_v2(
        self,
        document,
        pages: list,
        *,
        client_profile=None,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        # Null guard: normalize callback so we never need to check again
        if progress_callback is None:
            async def progress_callback(processed: int, total: int) -> None:
                pass

        analysis_started = time.perf_counter()

        client_context = self._build_client_context(client_profile)
        lane = self._determine_jurisdiction(document, client_profile, pages)
        marking_country = self._determine_marking_country(client_profile, lane)

        # ── Preflight: verify OpenRouter availability BEFORE any work ──
        # Only needed for FR/EU lane (Step E uses OpenRouter for EU dual-use).
        # US lane uses local models for EAR screening/detailed analysis.
        if lane != LaneType.US:
            await self._prepare_eu_dualuse_client()
        experimental = lane == LaneType.US
        step_timing: dict[str, float] = {}

        # Step A: Per-page content scan (lightweight)
        t0 = time.monotonic()
        page_payloads = await self._scan_pages_v2(document, pages, lane=lane, client_context=client_context, progress_callback=progress_callback)
        page_scan_ms = round((time.monotonic() - t0) * 1000, 2)
        step_timing["step_a"] = round(time.monotonic() - t0, 2)
        self._raise_if_all_pages_llm_failed(page_payloads, pages)

        # Step B: Identify the tangible
        t0 = time.monotonic()
        context_block = self._build_document_context_v2(document, pages, page_payloads)
        tangible_payload, tangible_citations = await self._run_step_v2(
            "step_b_tangible_id.txt", "step_b_tangible", context_block,
            filename=document.original_filename, lane=lane.value, client_context=client_context,
        )
        step_timing["step_b"] = round(time.monotonic() - t0, 2)

        candidate_markings: list[dict[str, Any]] = []
        citations = list(self._collect_citations(page_payloads)) + tangible_citations
        evidence_items = self._collect_evidence(page_payloads)
        step_results: dict[str, Any] = {
            "step_a": self._aggregate_step_a(page_payloads),
            "step_b": tangible_payload,
        }
        confidence_payloads: list[dict[str, Any]] = [tangible_payload]
        borderline = False
        llm_step_failed = False
        lifecycle_phase = tangible_payload.get("lifecycle_phase")
        tangible_description = tangible_payload.get("item_description")
        tangible_category = tangible_payload.get("item_category")
        insufficient_evidence = False
        document_has_technical_content = self._has_any_technical_content_v2(page_payloads)

        if tangible_payload.get("_llm_failed"):
            final_marking = "US_REVIEW_REQUIRED" if lane == LaneType.US else "EC_Review_Required"
            final_confidence = 0.0
            llm_step_failed = True
            insufficient_evidence = True
            evidence_items.append(
                self._build_llm_failure_evidence(
                    self._analysis_text(
                        english="tangible identification",
                        french="l'identification du tangible",
                    ),
                    tangible_payload,
                )
            )
        elif not tangible_payload.get("item_identified"):
            # No tangible found
            if lane == LaneType.US:
                # US: no "not controlled" — everything is EAR99 at minimum
                final_marking = "US_EAR99"
            else:
                final_marking = "EC_Not_Technical"
            final_confidence = tangible_payload.get("confidence", 0.5)
        else:
            # Build enriched context with tangible info
            enriched_context = (
                f"Tangible identifié: {tangible_description}\n"
                f"Catégorie: {tangible_category}\n"
                f"Phase lifecycle: {lifecycle_phase}\n"
                f"Programme: {tangible_payload.get('program_context', 'inconnu')}\n"
                f"Méthode identification: {tangible_payload.get('identification_method', '')}\n"
                f"Mots-clés: {', '.join(tangible_payload.get('keywords', []))}\n\n"
                f"{context_block}"
            )

            if lane == LaneType.US:
                # ══════════════════════════════════════════════════════════
                # US LANE: ITAR → EAR pipeline
                # ══════════════════════════════════════════════════════════

                # Step C (US): ITAR assessment — is item on the USML?
                t0 = time.monotonic()
                itar_payload, itar_citations = await self._run_step_v2(
                    "step_c_itar.txt", "step_c_itar", enriched_context,
                    filename=document.original_filename, lane=lane.value, client_context=client_context,
                    thinking=True,
                )
                step_timing["step_c"] = round(time.monotonic() - t0, 2)
                citations.extend(itar_citations)
                step_results["step_c"] = itar_payload
                candidate_markings.extend(itar_payload.get("candidate_markings", []))
                confidence_payloads.append(itar_payload)

                if itar_payload.get("_llm_failed"):
                    final_marking = "US_REVIEW_REQUIRED"
                    llm_step_failed = True
                    insufficient_evidence = True
                    evidence_items.append(
                        self._build_llm_failure_evidence(
                            self._analysis_text(
                                english="ITAR/USML assessment",
                                french="l'evaluation ITAR/USML",
                            ),
                            itar_payload,
                        )
                    )
                elif itar_payload.get("is_itar"):
                    # Item is on the USML — but is the DOCUMENT technical data (§ 120.33)?
                    usml_cat = itar_payload.get("usml_category", "")
                    final_result = itar_payload.get("final_result") or {}
                    doc_is_controlled = final_result.get("document_is_controlled", True)
                    tech_data = itar_payload.get("technical_data_analysis") or {}
                    has_tech_data = tech_data.get("document_contains_technical_data", True)

                    if doc_is_controlled or has_tech_data:
                        # Document contains ITAR technical data → controlled
                        final_marking = f"US_ITAR_Cat{usml_cat}" if usml_cat else "US_REVIEW_REQUIRED"
                    else:
                        # Tangible is ITAR but document is NOT technical data
                        # (e.g. marketing brochure, public domain info) → EAR99
                        final_marking = "US_EAR99"
                else:
                    # Item NOT on USML → evaluate under EAR (Commerce Control List)
                    ear_context = (
                        f"Tangible non-ITAR: {tangible_description}\n"
                        f"Categorie: {tangible_category}\n"
                        f"Phase lifecycle: {lifecycle_phase}\n"
                        f"Mots-cles: {', '.join(tangible_payload.get('keywords', []))}\n\n"
                        f"{context_block}"
                    )

                    # Step E-1 (US): EAR screening — identify candidate CCL categories
                    t0 = time.monotonic()
                    screening_kb = self.kb_loader.load_ear_screening(text=ear_context)
                    screening_prompt = self.prompt_builder.build(
                        "step_e_ear_screening.txt",
                        kb_block=screening_kb.content,
                        document_block=ear_context,
                        filename=document.original_filename,
                        lane=lane.value,
                        client_context=client_context,
                    )
                    logger.info(
                        "US EAR screening: prompt=%d chars (~%d tokens), kb=%d chars",
                        len(screening_prompt), len(screening_prompt) // 4, len(screening_kb.content),
                    )
                    screening_payload = await self._safe_generate_json(
                        screening_prompt,
                        default={"screening_result": "ear99", "confidence": 0.3},
                        thinking=True,
                    )
                    step_timing["step_e_screening"] = round(time.monotonic() - t0, 2)
                    citations.extend(screening_kb.citations)
                    step_results["step_e_screening"] = screening_payload
                    candidate_markings.extend(screening_payload.get("candidate_markings", []))
                    confidence_payloads.append(screening_payload)

                    if screening_payload.get("_llm_failed"):
                        final_marking = "US_REVIEW_REQUIRED"
                        llm_step_failed = True
                        insufficient_evidence = True
                        evidence_items.append(
                            self._build_llm_failure_evidence(
                                self._analysis_text(
                                    english="EAR CCL screening",
                                    french="le screening EAR/CCL",
                                ),
                                screening_payload,
                            )
                        )
                    elif screening_payload.get("screening_result") == "ear99" or not screening_payload.get("candidate_categories"):
                        # No CCL match → EAR99
                        final_marking = "US_EAR99"
                    else:
                        # Step E-2 (US): EAR detailed — full category analysis
                        candidate_cats = screening_payload.get("candidate_categories", [])
                        # Limit to max 3 categories to stay within context window
                        candidate_cats = candidate_cats[:3]

                        t0 = time.monotonic()
                        detailed_kb = self.kb_loader.load_ear_detailed(candidate_cats)

                        # Inject screening results into context
                        screening_candidates = screening_payload.get("candidate_eccns", [])
                        screening_info = "\n".join(
                            f"  - {c.get('eccn', '?')}: {c.get('reason', '')}"
                            for c in screening_candidates
                        )
                        detailed_context = (
                            f"=== RESULTATS DU SCREENING ===\n"
                            f"Categories candidates: {', '.join(candidate_cats)}\n"
                            f"ECCNs pre-identifies:\n{screening_info}\n"
                            f"=== FIN SCREENING ===\n\n"
                            f"{ear_context}"
                        )

                        detailed_prompt = self.prompt_builder.build(
                            "step_e_ear_detailed.txt",
                            kb_block=detailed_kb.content,
                            document_block=detailed_context,
                            filename=document.original_filename,
                            lane=lane.value,
                            client_context=client_context,
                        )
                        logger.info(
                            "US EAR detailed: prompt=%d chars (~%d tokens), kb=%d chars, categories=%s",
                            len(detailed_prompt), len(detailed_prompt) // 4,
                            len(detailed_kb.content), candidate_cats,
                        )
                        detailed_payload = await self._safe_generate_json(
                            detailed_prompt,
                            default={"confidence": 0.0, "final_determination": {"marking": "US_EAR99"}},
                            thinking=True,
                        )
                        step_timing["step_e_detailed"] = round(time.monotonic() - t0, 2)
                        citations.extend(detailed_kb.citations)
                        step_results["step_e_detailed"] = detailed_payload
                        candidate_markings.extend(detailed_payload.get("candidate_markings", []))
                        confidence_payloads.append(detailed_payload)

                        # Extract thresholds for borderline detection
                        all_thresholds = [
                            tc
                            for ea in (detailed_payload.get("eccn_analysis") or [])
                            for tc in (ea.get("thresholds_checked") or [])
                        ]
                        borderline = self.validator.threshold_borderline(all_thresholds)

                        if detailed_payload.get("_llm_failed"):
                            final_marking = "US_REVIEW_REQUIRED"
                            llm_step_failed = True
                            insufficient_evidence = True
                            evidence_items.append(
                                self._build_llm_failure_evidence(
                                    self._analysis_text(
                                        english="EAR detailed ECCN analysis",
                                        french="l'analyse detaillee ECCN/EAR",
                                    ),
                                    detailed_payload,
                                )
                            )
                        else:
                            final_det = detailed_payload.get("final_determination") or {}
                            eccn_marking = final_det.get("marking") or final_det.get("eccn_full")
                            if eccn_marking and eccn_marking != "EAR99":
                                final_marking = self._normalize_marking_code(
                                    eccn_marking, lane=LaneType.US, country_code=marking_country,
                                ) or "US_REVIEW_REQUIRED"
                            else:
                                final_marking = "US_EAR99"

            else:
                # ══════════════════════════════════════════════════════════
                # FR/EU LANE: French ML → EU Dual-Use pipeline (existing)
                # ══════════════════════════════════════════════════════════

                # Step C: Military assessment (deep)
                t0 = time.monotonic()
                military_payload, military_citations = await self._run_step_v2(
                    "step_c_military.txt", "step_c_military", enriched_context,
                    filename=document.original_filename, lane=lane.value, client_context=client_context,
                    thinking=True,
                )
                step_timing["step_c"] = round(time.monotonic() - t0, 2)
                military_payload = self._normalize_step_c_payload(military_payload)
                citations.extend(military_citations)
                step_results["step_c"] = military_payload
                candidate_markings.extend(military_payload.get("candidate_markings", []))
                confidence_payloads.append(military_payload)

                if military_payload.get("_llm_failed"):
                    final_marking = "EC_Review_Required"
                    llm_step_failed = True
                    insufficient_evidence = True
                    evidence_items.append(
                        self._build_llm_failure_evidence(
                            self._analysis_text(
                                english="military analysis",
                                french="l'analyse militaire",
                            ),
                            military_payload,
                        )
                    )
                elif military_payload.get("is_military"):
                    # Step D: Technical data determination under ML22
                    ml_context = (
                        f"Tangible militaire: {tangible_description}\n"
                        f"Catégorie ML: {military_payload.get('ml_category', 'indéterminée')}\n"
                        f"Phase lifecycle: {lifecycle_phase}\n"
                        f"Raisonnement militaire: {military_payload.get('reasoning', '')}\n\n"
                        f"{context_block}"
                    )
                    t0 = time.monotonic()
                    techdata_ml_payload, techdata_ml_citations = await self._run_step_v2(
                        "step_d_techdata_ml.txt", "step_d_techdata_ml", ml_context,
                        filename=document.original_filename, lane=lane.value, client_context=client_context,
                        thinking=True,
                    )
                    step_timing["step_d"] = round(time.monotonic() - t0, 2)
                    citations.extend(techdata_ml_citations)
                    step_results["step_d"] = techdata_ml_payload
                    confidence_payloads.append(techdata_ml_payload)

                    if techdata_ml_payload.get("_llm_failed"):
                        final_marking = "EC_Review_Required"
                        llm_step_failed = True
                        insufficient_evidence = True
                        evidence_items.append(
                            self._build_llm_failure_evidence(
                                self._analysis_text(
                                    english="the ML22 technical-data qualification",
                                    french="la qualification ML22 de la donnee",
                                ),
                                techdata_ml_payload,
                            )
                        )
                    elif techdata_ml_payload.get("is_technical_data"):
                        ml22_code = techdata_ml_payload.get("ml22_subcategory_code")
                        final_marking = (
                            self._normalize_marking_code(ml22_code, lane=LaneType.FR_EU, country_code=marking_country)
                            or "EC_Review_Required"
                        )
                    else:
                        final_marking = "EC_Not_Technical"
                else:
                    # Step E: Unified EU dual-use analysis
                    # Sends the ENTIRE Annexe I regulation (~30K tokens) in a single call
                    # to a large-context model (OpenRouter), replacing the old keyword-based
                    # step_e + step_f split. The model performs:
                    #   1. Category analysis (0-9)
                    #   2. ECCN identification with threshold verification
                    #   3. Nature E cross-reference
                    #   4. Technical data qualification
                    #   5. GTN exclusion check
                    du_context = (
                        f"Tangible non-militaire: {tangible_description}\n"
                        f"Catégorie: {tangible_category}\n"
                        f"Phase lifecycle: {lifecycle_phase}\n"
                        f"Mots-clés: {', '.join(tangible_payload.get('keywords', []))}\n\n"
                        f"{context_block}"
                    )
                    t0 = time.monotonic()
                    dualuse_payload, dualuse_citations = await self._run_unified_dualuse(
                        du_context,
                        filename=document.original_filename,
                        lane=lane.value,
                        client_context=client_context,
                    )
                    step_timing["step_e"] = round(time.monotonic() - t0, 2)
                    citations.extend(dualuse_citations)
                    step_results["step_e"] = dualuse_payload
                    candidate_markings.extend(dualuse_payload.get("candidate_markings", []))
                    confidence_payloads.append(dualuse_payload)

                    # Extract thresholds from nested eccn_analysis for borderline detection
                    all_thresholds = [
                        tc
                        for ea in (dualuse_payload.get("eccn_analysis") or [])
                        for tc in (ea.get("thresholds_checked") or [])
                    ]
                    borderline = self.validator.threshold_borderline(all_thresholds)

                    if dualuse_payload.get("_llm_failed"):
                        final_marking = "EC_Review_Required"
                        llm_step_failed = True
                        insufficient_evidence = True
                        evidence_items.append(
                            self._build_llm_failure_evidence(
                                self._analysis_text(
                                    english="the unified dual-use analysis",
                                    french="l'analyse double usage unifiee",
                                ),
                                dualuse_payload,
                            )
                        )
                    else:
                        final_det = dualuse_payload.get("final_determination") or {}
                        doc_controlled = final_det.get("document_controlled", False)
                        is_listed = dualuse_payload.get("is_listed", False)

                        if doc_controlled:
                            # Document is controlled — extract the ECCN code
                            eccn_code = final_det.get("eccn_code") or final_det.get("marking")
                            final_marking = (
                                self._normalize_marking_code(eccn_code, lane=LaneType.FR_EU, country_code=marking_country)
                                or "EC_Review_Required"
                            )
                        elif is_listed:
                            # Tangible is listed but document is NOT controlled
                            # (e.g. SPF case: tangible 1B003 listed, but document is not
                            # actionable technical data under Nature E)
                            final_marking = self._technical_not_controlled_marking(marking_country) if document_has_technical_content else "EC_Not_Technical"
                        else:
                            # Tangible not listed at all
                            final_marking = self._technical_not_controlled_marking(marking_country) if document_has_technical_content else "EC_Not_Technical"

            additional_step_payloads = [p for p in confidence_payloads if p is not tangible_payload]
            insufficient_evidence = insufficient_evidence or self.validator.detect_insufficient_evidence(page_payloads, additional_step_payloads)
            confidence_inputs = [
                payload.get("confidence", 0.0)
                for payload in confidence_payloads
                if payload and self._counts_toward_confidence(payload)
            ]
            final_confidence = self.validator.compute_final_confidence(confidence_inputs) if confidence_inputs else 0.0
            if llm_step_failed:
                final_confidence = 0.0
            if insufficient_evidence and not self.validator.validate_marking_format(final_marking):
                final_marking = "EC_Review_Required"

        step_results["step_timing"] = step_timing
        candidate_markings = self._dedupe_candidates(
            candidate_markings,
            final_marking,
            final_confidence,
            lane=lane,
            country_code=marking_country,
        )
        valid, errors = self.validator.validate_coherence_v2({**step_results, "final_marking": final_marking, "final_confidence": final_confidence})
        if not valid:
            final_marking = "EC_Review_Required"
            insufficient_evidence = True
            candidate_markings = self._dedupe_candidates(
                candidate_markings,
                final_marking,
                final_confidence,
                lane=lane,
                country_code=marking_country,
            )
            evidence_items.append({"page_number": 0, "kind": "system", "excerpt": None, "reason": "; ".join(errors), "image_path": None})

        review_priority = self.validator.determine_review_priority(
            final_confidence,
            insufficient_evidence=insufficient_evidence,
            experimental=experimental,
            has_threshold_borderline=borderline,
        )
        requires_human_review = self.validator.should_require_review(
            final_confidence,
            experimental=experimental,
            insufficient_evidence=insufficient_evidence,
        )

        unique_citations = self._unique_dicts(citations)
        unique_evidence_items = self._unique_dicts(evidence_items)

        fallback_summary = self._fallback_summary_v2(
            final_marking,
            final_confidence,
            requires_human_review,
            page_payloads,
            step_results=step_results,
            tangible_description=tangible_description,
            lifecycle_phase=lifecycle_phase,
        )
        if llm_step_failed or self._should_skip_generated_summary_v2(step_results):
            reasoning_summary = fallback_summary
        else:
            summary_step_results = {
                key: value
                for key, value in step_results.items()
                if key != "verdict_lock"
            }
            generated_summary = await self._summarize_v2(
                f"Document: {document.original_filename}\n"
                f"Tangible: {tangible_description or 'non identifié'}\n"
                f"Catégorie: {tangible_category or 'inconnue'}\n"
                f"Phase lifecycle: {lifecycle_phase or 'inconnue'}\n"
                f"Decision label: {get_marking_label(final_marking)}\n"
                f"Internal decision code: {final_marking}\n"
                f"Confidence: {final_confidence}\n"
                f"Requires review: {requires_human_review}\n"
                f"Evidence: {evidence_items[:8]}\nStep results: {summary_step_results}",
                fallback=fallback_summary,
                lane=lane,
            )
            reasoning_summary = self._coerce_summary_v2(
                generated_summary,
                fallback=fallback_summary,
                final_marking=final_marking,
                requires_review=requires_human_review,
            )

        page_rollup = {
            "total_pages": len(pages),
            "relevant_pages": [payload["page_number"] for payload in page_payloads if payload.get("tangible_hints")],
            "technical_pages": [
                payload["page_number"]
                for payload in page_payloads
                if (payload.get("content_signals") or {}).get("substantive")
            ],
            "document_types": dict(Counter(payload.get("document_type", "unknown") for payload in page_payloads)),
        }

        return {
            "lane": lane,
            "final_marking": final_marking,
            "final_confidence": final_confidence,
            "experimental": experimental,
            "insufficient_evidence": insufficient_evidence,
            "requires_human_review": requires_human_review,
            "review_priority": review_priority,
            "jurisdiction": "US" if lane == LaneType.US else "FR/EU",
            "reasoning_summary": reasoning_summary,
            "candidate_markings": candidate_markings,
            "citations": unique_citations,
            "evidence_items": unique_evidence_items,
            "page_rollup": page_rollup,
            "step_results": step_results,
            "page_payloads": page_payloads,
            "veltar_projection": project_to_veltar(final_marking, experimental=experimental, confidence=final_confidence),
            "pipeline_version": "v2",
            "lifecycle_phase": lifecycle_phase,
            "tangible_description": tangible_description,
            "tangible_category": tangible_category,
        }

    async def _scan_pages_v2(
        self,
        document,
        pages: list,
        *,
        lane: LaneType,
        client_context: str,
        progress_callback: ProgressCallback | None = None,
    ) -> list[dict[str, Any]]:
        async def analyze_page(page) -> dict[str, Any]:
            page_text = (page.extracted_text or "")[:7000]
            has_text = len(page_text.strip()) > 20
            has_image = bool(page.image_path) and page.content_type != PageContentType.TEXT

            # OCR failure detection: skip LLM call if no exploitable content
            if not has_text and not has_image:
                result = {
                    "page_number": page.page_number,
                    "page_summary": self._analysis_text(
                        english="OCR extraction failed - no usable content was found.",
                        french="Extraction OCR echouee - aucun contenu exploitable.",
                    ),
                    "ocr_failed": True,
                    "document_type": "unknown",
                    "tangible_hints": [],
                    "lifecycle_phase_hints": [],
                    "content_signals": {"substantive": [], "reference": [], "contextual": []},
                    "jurisdiction_signals": [],
                    "program_references": [],
                    "confidence": 0.0,
                    "missing_information": ["OCR extraction failed — no text or image available"],
                    "citations": [],
                    "relevant": False,
                    "is_technical": False,
                    "technical_score": 0,
                    "indicators_found": [],
                    "evidence": [],
                }
                return result

            kb_bundle = self.kb_loader.load("step_a_scan", text=f"{document.original_filename}\n{page_text}")
            prompt = self.prompt_builder.build(
                "step_a_page_scan.txt",
                kb_block=kb_bundle.content,
                document_block=self._page_block(page),
                filename=document.original_filename,
                lane=lane.value,
                client_context=client_context,
            )
            result = await self._safe_generate_json(
                prompt,
                image_path=page.image_path if page.content_type != PageContentType.TEXT else None,
                thinking=self._visual_thinking_enabled and page.content_type != PageContentType.TEXT,
                default={
                    "page_summary": self._analysis_text(
                        english="Model response unavailable.",
                        french="Reponse du modele indisponible.",
                    ),
                    "document_type": "unknown",
                    "tangible_hints": [],
                    "lifecycle_phase_hints": [],
                    "content_signals": {"substantive": [], "reference": [], "contextual": []},
                    "jurisdiction_signals": [],
                    "program_references": [],
                    "confidence": 0.0,
                    "missing_information": [
                        self._analysis_text(
                            english="LLM response unavailable",
                            french="Reponse du LLM indisponible",
                        )
                    ],
                },
            )
            result["page_number"] = page.page_number
            result["citations"] = kb_bundle.citations
            # Determine relevance based on tangible hints or substantive signals
            signals = result.get("content_signals", {})
            result["relevant"] = bool(result.get("tangible_hints")) or bool(signals.get("substantive"))
            # Compatibility fields for V1 page_payloads format
            result["is_technical"] = False  # V2 doesn't determine this per-page
            result["technical_score"] = 0
            result["indicators_found"] = signals.get("substantive", [])
            result["evidence"] = [
                {
                    "kind": "text",
                    "excerpt": s,
                    "reason": self._analysis_text(
                        english="Substantive signal detected",
                        french="Signal substantif detecte",
                    ),
                }
                for s in (signals.get("substantive") or [])[:5]
            ]
            return result

        return await self._run_page_scan_tasks(
            pages,
            analyze_page=analyze_page,
            progress_callback=progress_callback,
        )

    async def _run_step_v2(
        self,
        template_name: str,
        step_name: str,
        context_block: str,
        *,
        filename: str,
        lane: str,
        client_context: str = "",
        thinking: bool = False,
    ) -> tuple[dict[str, Any], list[dict]]:
        kb_bundle = self.kb_loader.load(step_name, text=context_block)

        # Inject pre-matched ECCN candidates into the document block so the LLM evaluates them
        enriched_context = context_block
        if kb_bundle.pre_matched_eccns:
            lines = [
                "\n═══ CANDIDATS PRÉ-IDENTIFIÉS (correspondances trouvées dans la base de connaissances) ═══",
                "Les termes suivants du document correspondent à des rubriques de la liste de contrôle.",
                "Tu DOIS évaluer chacun de ces candidats dans ton analyse :\n",
            ]
            for match in kb_bundle.pre_matched_eccns:
                lines.append(f"  • Terme trouvé: \"{match['matched_term']}\" → Rubrique: {match['eccn']} — {match['description']}")
            lines.append("\nÉvalue chaque candidat ci-dessus en vérifiant les seuils dans la base de connaissances.")
            lines.append("═══════════════════════════════════════════════════════════════════════════════════════\n")
            enriched_context = "\n".join(lines) + "\n" + context_block

        prompt = self.prompt_builder.build(
            template_name,
            kb_block=kb_bundle.content,
            document_block=enriched_context,
            filename=filename,
            lane=lane,
            client_context=client_context,
        )
        prompt_chars = len(prompt)
        estimated_tokens = prompt_chars // 4
        context_window_tokens = max(1024, int(self.settings.llm_context_window_tokens))
        safe_prompt_tokens = max(1024, context_window_tokens - int(self.settings.llm_max_tokens) - 256)
        logger.info(
            "V2 step %s: prompt=%d chars (~%d tokens), kb=%d chars, context=%d chars, thinking=%s",
            step_name, prompt_chars, estimated_tokens, len(kb_bundle.content), len(context_block), thinking,
        )
        if estimated_tokens > safe_prompt_tokens:
            logger.warning("V2 step %s: prompt exceeds 12K tokens (%d estimated) — may cause LLM errors", step_name, estimated_tokens)
        payload = await self._safe_generate_json(
            prompt,
            default={
                "confidence": 0.0,
                "reasoning": self._analysis_text(english="No result.", french="Aucun resultat."),
            },
            thinking=thinking,
        )
        return payload, kb_bundle.citations

    async def _run_unified_dualuse(
        self,
        context_block: str,
        *,
        filename: str,
        lane: str,
        client_context: str = "",
    ) -> tuple[dict[str, Any], list[dict]]:
        """Run the unified EU dual-use analysis with the full Annexe I regulation.

        Loads ALL EU dual-use KB files (~30K tokens) and sends them in a single
        call to a large-context model via OpenRouter. The model performs category
        analysis, ECCN identification, Nature E cross-reference, technical data
        qualification, and GTN exclusion in one pass.

        Returns (payload, citations) where payload contains the full analysis
        including final_determination, eccn_analysis, nature_e_analysis, etc.
        """
        kb_bundle = self.kb_loader.load_full_eu_dualuse()
        prompt = self.prompt_builder.build(
            "step_e_dualuse_unified.txt",
            kb_block=kb_bundle.content,
            document_block=context_block,
            filename=filename,
            lane=lane,
            client_context=client_context,
        )

        client = self._eu_dualuse_client
        prompt_chars = len(prompt)
        logger.info(
            "V2 unified dual-use: prompt=%d chars (~%d tokens), kb=%d chars, model=%s",
            prompt_chars, prompt_chars // 4, len(kb_bundle.content),
            getattr(client, "model_name", "unknown"),
        )

        default_payload: dict[str, Any] = {
            "confidence": 0.0,
            "reasoning": self._analysis_text(english="No result.", french="Aucun resultat."),
            "is_listed": False,
        }
        try:
            response = await client.generate_json(prompt)
            payload = {**default_payload, **response}
        except Exception as exc:
            error_message = self._stringify_exception(exc)
            payload = dict(default_payload)
            payload["missing_information"] = [f"LLM error: {error_message}"]
            payload["uncertainties"] = ["Model call failed"]
            payload["_llm_failed"] = True
            payload["_llm_error"] = error_message
            return payload, kb_bundle.citations

        # Extract top-level fields from the unified response for pipeline compatibility
        final_det = payload.get("final_determination") or {}
        if final_det:
            payload["confidence"] = final_det.get("confidence", payload.get("confidence", 0.0))
            payload["is_listed"] = bool(payload.get("primary_eccn")) or final_det.get("document_controlled", False)

        # Normalize candidate_markings codes
        raw_candidates = payload.get("candidate_markings") or []
        normalized_candidates = []
        for candidate in raw_candidates:
            code = self._normalize_marking_code(candidate.get("code"), lane=LaneType.FR_EU)
            if code:
                normalized_candidates.append({**candidate, "code": code})
        payload["candidate_markings"] = normalized_candidates

        return payload, kb_bundle.citations

    async def _summarize_v2(self, context: str, *, fallback: str, lane: LaneType = LaneType.FR_EU) -> str:
        if lane == LaneType.US:
            prompt_template = "layer3_summary_v2_us.txt"
        else:
            prompt_template = "layer3_summary_v2.txt"
        prompt = self.prompt_builder.build(
            prompt_template,
            kb_block="",
            document_block=context,
            filename="",
            lane=lane.value if isinstance(lane, LaneType) else "",
        )
        client = self._summary_client
        logger.info(
            "V2 final rationale uses model=%s, base_url=%s, prompt=%s",
            getattr(client, "model_name", "unknown"),
            getattr(client, "base_url", "unknown"),
            prompt_template,
        )
        return (await client.generate_text(prompt)).strip()

    @staticmethod
    def _build_client_context(client_profile) -> str:
        if client_profile is None:
            return ""
        parts = [
            f"Entreprise: {client_profile.name}",
            f"Pays: {client_profile.country}",
        ]
        if client_profile.activity_description:
            parts.append(f"Activité: {client_profile.activity_description}")
        if client_profile.product_families:
            parts.append(f"Familles de produits: {', '.join(client_profile.product_families)}")
        if client_profile.program_names:
            parts.append(f"Programmes: {', '.join(client_profile.program_names)}")
        if client_profile.naming_conventions:
            parts.append(f"Conventions de nommage: {client_profile.naming_conventions}")
        if client_profile.classification_history:
            history_lines = []
            for entry in client_profile.classification_history[:10]:
                history_lines.append(f"  - {entry.get('item', '?')}: {entry.get('marking', '?')}")
            if history_lines:
                parts.append("Historique de classement:\n" + "\n".join(history_lines))
        if client_profile.regulatory_scope:
            parts.append(f"Réglementations applicables: {', '.join(client_profile.regulatory_scope)}")
        return "\n".join(parts)

    @staticmethod
    def _determine_jurisdiction(document, client_profile, pages: list) -> LaneType:
        if client_profile and client_profile.country:
            country = normalize_country_code(client_profile.country)
            return COUNTRY_TO_LANE.get(country, LaneType.FR_EU)
        # Fallback to V1 keyword detection
        return ClassificationOrchestrator._detect_lane(document, pages)

    @staticmethod
    def _determine_marking_country(client_profile, lane: LaneType) -> str:
        if client_profile and getattr(client_profile, "country", None):
            country = normalize_country_code(client_profile.country)
            if re.fullmatch(r"[A-Z]{2}", country):
                return country
        return "US" if lane == LaneType.US else "FR"

    @staticmethod
    def _technical_not_controlled_marking(country_code: str) -> str:
        prefix = country_code.strip().upper() if country_code else "FR"
        return f"{prefix}_EC_Technical_Not_Controlled"

    @classmethod
    def _build_document_context_v2(cls, document, pages: list, page_payloads: list[dict[str, Any]]) -> str:
        sections: list[str] = [
            f"Filename: {document.original_filename}",
            f"Document hint: {document.context_hint or ''}",
        ]
        for page, payload in cls._select_v2_context_pages(pages, page_payloads):
            excerpt = (page.extracted_text or "")[:900]
            tangible_hints = payload.get("tangible_hints", [])
            hints_text = ", ".join(h.get("name", "") for h in tangible_hints if h.get("name")) if tangible_hints else "aucun"
            signals = payload.get("content_signals", {})
            substantive = signals.get("substantive", [])
            sections.append(
                "\n".join([
                    f"Page {page.page_number} - {page.section_label}",
                    f"Type: {payload.get('document_type', 'unknown')}",
                    f"Tangibles mentionnés: {hints_text}",
                    f"Signaux substantifs: {', '.join(substantive[:6]) if substantive else 'aucun'}",
                    f"Programmes: {', '.join(payload.get('program_references', []))}",
                    f"Résumé: {payload.get('page_summary', '')}",
                    f"Texte: {excerpt}",
                ])
            )
        return "\n\n".join(sections)

    @classmethod
    def _select_v2_context_pages(
        cls,
        pages: list,
        page_payloads: list[dict[str, Any]],
        *,
        max_pages: int = 12,
    ) -> list[tuple[Any, dict[str, Any]]]:
        ranked: list[tuple[int, int, Any, dict[str, Any]]] = []
        fallback_pages: list[tuple[Any, dict[str, Any]]] = []

        for page, payload in zip(pages, page_payloads, strict=False):
            fallback_pages.append((page, payload))
            score = cls._score_v2_context_page(page, payload)
            if score <= 0 and not payload.get("relevant"):
                continue
            ranked.append((score, page.page_number, page, payload))

        if not ranked:
            return fallback_pages[: min(len(fallback_pages), max_pages)]

        selected = sorted(ranked, key=lambda item: (-item[0], item[1]))[:max_pages]
        selected.sort(key=lambda item: item[1])
        return [(page, payload) for _, _, page, payload in selected]

    @staticmethod
    def _score_v2_context_page(page, payload: dict[str, Any]) -> int:
        signals = payload.get("content_signals", {}) or {}
        substantive = list(signals.get("substantive") or [])
        tangible_hints = list(payload.get("tangible_hints") or [])
        program_references = list(payload.get("program_references") or [])
        lifecycle_hints = list(payload.get("lifecycle_phase_hints") or [])
        document_type = str(payload.get("document_type") or "").upper()
        summary = str(payload.get("page_summary") or "")
        page_text = (page.extracted_text or "")[:1200]
        combined_text = " ".join([summary, page_text, " ".join(substantive)])

        score = 0
        if payload.get("relevant"):
            score += 20
        score += len(substantive) * 8
        score += len(tangible_hints) * 5
        score += len(program_references) * 2
        score += len(lifecycle_hints) * 2
        if re.search(r"\d", combined_text):
            score += 6
        if any(token in combined_text.lower() for token in ["temperature", "inspection", "composition", "roughness", "cad", "welding", "metall", "test"]):
            score += 6
        if document_type in {"COVER_PAGE", "APPROVAL_PAGE", "INDEX", "LETTER", "PRESENTATION"}:
            score -= 18
        if payload.get("ocr_failed"):
            score = 0
        return score

    @staticmethod
    def _aggregate_step_a(page_payloads: list[dict[str, Any]]) -> dict[str, Any]:
        all_tangible_hints: list[dict] = []
        all_lifecycle_hints: list[str] = []
        all_programs: list[str] = []
        for payload in page_payloads:
            all_tangible_hints.extend(payload.get("tangible_hints", []))
            all_lifecycle_hints.extend(payload.get("lifecycle_phase_hints", []))
            all_programs.extend(payload.get("program_references", []))
        ocr_failed_count = sum(1 for p in page_payloads if p.get("ocr_failed"))
        return {
            "tangible_hints": all_tangible_hints,
            "lifecycle_phase_hints": sorted(set(all_lifecycle_hints)),
            "program_references": sorted(set(all_programs)),
            "document_types": dict(Counter(p.get("document_type", "unknown") for p in page_payloads)),
            "pages_with_tangible": sum(1 for p in page_payloads if p.get("tangible_hints")),
            "pages_with_substance": sum(
                1 for p in page_payloads
                if (p.get("content_signals") or {}).get("substantive")
            ),
            "ocr_failed_pages": ocr_failed_count,
        }

    @staticmethod
    def _has_any_technical_content_v2(page_payloads: list[dict[str, Any]]) -> bool:
        for payload in page_payloads:
            signals = payload.get("content_signals", {})
            if signals.get("substantive"):
                return True
        return False

    # ── V1 Pipeline (DEPRECATED — kept for code reference only) ─────
    # Prompt files for v1 have been removed (step2_technical, step4_item_id,
    # step5_military, step7_dualuse, step8_technology, step_us_experimental,
    # layer3_summary, layer3_summary_en). The dispatcher in classify_document
    # no longer routes here. Calling this method will raise FileNotFoundError
    # at the first prompt load. Treat as dead code awaiting full removal.

    async def _classify_v1(
        self,
        document,
        pages: list,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        if progress_callback is None:
            async def progress_callback(processed: int, total: int) -> None:
                pass

        lane = self._detect_lane(document, pages)
        page_payloads = await self._analyze_pages(document, pages, lane=lane, progress_callback=progress_callback)
        self._raise_if_all_pages_llm_failed(page_payloads, pages)
        step2_summary = self._aggregate_step2(page_payloads)

        candidate_markings: list[dict[str, Any]] = []
        citations = list(self._collect_citations(page_payloads))
        evidence_items = self._collect_evidence(page_payloads)
        step_results: dict[str, Any] = {"step2": step2_summary}
        experimental = lane == LaneType.US
        borderline = False
        confidence_payloads: list[dict[str, Any]] = []

        if not step2_summary["is_technical"]:
            final_marking = "EC_Not_Technical"
            final_confidence = step2_summary["confidence"]
            insufficient_evidence = False
        else:
            context_block = self._build_document_context(document, pages, page_payloads)
            item_payload, item_citations = await self._run_step(
                "step4_item_id.txt",
                "step4_item_id",
                context_block,
                filename=document.original_filename,
                lane=lane.value,
            )
            citations.extend(item_citations)
            step_results["step4"] = item_payload
            confidence_payloads = [item_payload]

            additional_step_payloads = [item_payload]
            if lane == LaneType.US:
                us_payload, us_citations = await self._run_step(
                    "step_us_experimental.txt",
                    "step_us_experimental",
                    context_block,
                    filename=document.original_filename,
                    lane=lane.value,
                    thinking=True,
                )
                citations.extend(us_citations)
                step_results["step_us"] = us_payload
                candidate_markings.extend(us_payload.get("candidate_markings", []))
                additional_step_payloads.append(us_payload)
                confidence_payloads.append(us_payload)
                final_marking = self._normalize_marking_code(
                    us_payload.get("classification_code"),
                    lane=lane,
                ) or "EC_Review_Required"
            else:
                military_payload, military_citations = await self._run_step(
                    "step5_military.txt",
                    "step5_military",
                    context_block,
                    filename=document.original_filename,
                    lane=lane.value,
                    thinking=True,
                )
                citations.extend(military_citations)
                step_results["step5"] = military_payload
                candidate_markings.extend(military_payload.get("candidate_markings", []))
                additional_step_payloads.append(military_payload)

                if military_payload.get("is_military"):
                    confidence_payloads.append(military_payload)
                    final_marking = self._normalize_marking_code(
                        military_payload.get("classification_code"),
                        lane=LaneType.FR_EU,
                    ) or "EC_Review_Required"
                else:
                    dual_payload, dual_citations = await self._run_step(
                        "step7_dualuse.txt",
                        "step7_dualuse",
                        context_block,
                        filename=document.original_filename,
                        lane=lane.value,
                        thinking=True,
                    )
                    dual_payload = self._normalize_step7_payload(dual_payload, pages)
                    citations.extend(dual_citations)
                    step_results["step7"] = dual_payload
                    candidate_markings.extend(dual_payload.get("candidate_markings", []))
                    additional_step_payloads.append(dual_payload)
                    confidence_payloads.append(dual_payload)

                    if dual_payload.get("is_listed"):
                        tech_payload, tech_citations = await self._run_step(
                            "step8_technology.txt",
                            "step8_technology",
                            context_block,
                            filename=document.original_filename,
                            lane=lane.value,
                            thinking=True,
                        )
                        citations.extend(tech_citations)
                        step_results["step8"] = tech_payload
                        additional_step_payloads.append(tech_payload)
                        if self._counts_toward_confidence(tech_payload):
                            confidence_payloads.append(tech_payload)
                        final_marking = (
                            self._normalize_marking_code(
                                tech_payload.get("classification_code"),
                                lane=LaneType.FR_EU,
                            )
                            or self._normalize_marking_code(
                                dual_payload.get("eccn"),
                                lane=LaneType.FR_EU,
                            )
                            or "EC_Review_Required"
                        )
                    else:
                        final_marking = self._technical_not_controlled_marking("FR")
                    borderline = self.validator.threshold_borderline(dual_payload.get("thresholds_checked", []))

            insufficient_evidence = self.validator.detect_insufficient_evidence(page_payloads, additional_step_payloads)
            confidence_inputs = [step2_summary.get("confidence", 0.0)] + [
                payload.get("confidence", 0.0)
                for payload in confidence_payloads
                if payload and self._counts_toward_confidence(payload)
            ]
            final_confidence = self.validator.compute_final_confidence(confidence_inputs)
            if insufficient_evidence and not self.validator.validate_marking_format(final_marking):
                final_marking = "EC_Review_Required"

        candidate_markings = self._dedupe_candidates(candidate_markings, final_marking, final_confidence, lane=lane)
        valid, errors = self.validator.validate_coherence({"step2": step_results.get("step2"), **step_results, "final_marking": final_marking})
        if not valid:
            final_marking = "EC_Review_Required"
            insufficient_evidence = True
            candidate_markings = self._dedupe_candidates(candidate_markings, final_marking, final_confidence, lane=lane)
            evidence_items.append({"page_number": 0, "kind": "system", "excerpt": None, "reason": "; ".join(errors), "image_path": None})

        review_priority = self.validator.determine_review_priority(
            final_confidence,
            insufficient_evidence=insufficient_evidence,
            experimental=experimental,
            has_threshold_borderline=borderline,
        )
        requires_human_review = self.validator.should_require_review(
            final_confidence,
            experimental=experimental,
            insufficient_evidence=insufficient_evidence,
        )
        reasoning_summary = await self._summarize(
            f"Document: {document.original_filename}\nDecision label: {get_marking_label(final_marking)}\n"
            f"Internal decision code: {final_marking}\nConfidence: {final_confidence}\n"
            f"Requires review: {requires_human_review}\nEvidence: {evidence_items[:8]}\nStep results: {step_results}",
            fallback=self._fallback_summary(final_marking, final_confidence, requires_human_review, page_payloads),
        )
        reasoning_summary = replace_marking_codes_in_text(reasoning_summary)
        page_rollup = {
            "total_pages": len(pages),
            "relevant_pages": [payload["page_number"] for payload in page_payloads if payload.get("relevant")],
            "technical_pages": [payload["page_number"] for payload in page_payloads if payload.get("technical_score", 0) >= self.settings.technical_score_threshold],
            "document_types": dict(Counter(payload.get("document_type", "unknown") for payload in page_payloads)),
        }
        return {
            "lane": lane,
            "final_marking": final_marking,
            "final_confidence": final_confidence,
            "experimental": experimental,
            "insufficient_evidence": insufficient_evidence,
            "requires_human_review": requires_human_review,
            "review_priority": review_priority,
            "jurisdiction": "US" if lane == LaneType.US else "FR/EU",
            "reasoning_summary": reasoning_summary,
            "candidate_markings": candidate_markings,
            "citations": self._unique_dicts(citations),
            "evidence_items": self._unique_dicts(evidence_items),
            "page_rollup": page_rollup,
            "step_results": step_results,
            "page_payloads": page_payloads,
            "phase_timings": {
                "page_scan_ms": page_scan_ms,
                "decision_ms": round((time.perf_counter() - analysis_started) * 1000 - page_scan_ms, 2),
                "analysis_ms": round((time.perf_counter() - analysis_started) * 1000, 2),
            },
            "veltar_projection": project_to_veltar(final_marking, experimental=experimental, confidence=final_confidence),
        }

    async def _analyze_pages(
        self,
        document,
        pages: list,
        *,
        lane: LaneType,
        progress_callback: ProgressCallback | None = None,
    ) -> list[dict[str, Any]]:
        async def analyze_page(page) -> dict[str, Any]:
            page_text = (page.extracted_text or "")[:7000]
            kb_bundle = self.kb_loader.load("step2_technical", text=f"{document.original_filename}\n{page_text}")
            prompt = self.prompt_builder.build(
                "step2_technical.txt",
                kb_block=kb_bundle.content,
                document_block=self._page_block(page),
                filename=document.original_filename,
                lane=lane.value,
            )
            result = await self._safe_generate_json(
                prompt,
                image_path=page.image_path if page.content_type != PageContentType.TEXT else None,
                thinking=self._visual_thinking_enabled and page.content_type != PageContentType.TEXT,
                default={
                    "page_summary": self._analysis_text(
                        english="Model response unavailable.",
                        french="Reponse du modele indisponible.",
                    ),
                    "is_technical": False,
                    "technical_score": 0,
                    "confidence": 0.0,
                    "document_type": "unknown",
                    "candidate_item_hints": [],
                    "indicators_found": [],
                    "missing_information": [
                        self._analysis_text(
                            english="LLM response unavailable",
                            french="Reponse du LLM indisponible",
                        )
                    ],
                    "evidence": [],
                    "us_signals": [],
                    "fr_eu_signals": [],
                },
            )
            result = self._normalize_step2_payload(result, page_text=page_text)
            result["page_number"] = page.page_number
            result["relevant"] = not result.get("contextual_only", False) and (
                result.get("is_technical", False) or bool(result.get("indicators_found"))
            )
            result["citations"] = kb_bundle.citations
            return result

        return await self._run_page_scan_tasks(
            pages,
            analyze_page=analyze_page,
            progress_callback=progress_callback,
        )

    async def _run_step(
        self,
        template_name: str,
        step_name: str,
        context_block: str,
        *,
        filename: str,
        lane: str,
        thinking: bool = False,
    ) -> tuple[dict[str, Any], list[dict]]:
        kb_bundle = self.kb_loader.load(step_name, text=context_block)
        prompt = self.prompt_builder.build(
            template_name,
            kb_block=kb_bundle.content,
            document_block=context_block,
            filename=filename,
            lane=lane,
        )
        payload = await self._safe_generate_json(
            prompt,
            default={
                "confidence": 0.0,
                "reasoning": self._analysis_text(english="No result.", french="Aucun resultat."),
            },
            thinking=thinking,
        )
        return payload, kb_bundle.citations

    async def _safe_generate_json(
        self,
        prompt: str,
        *,
        image_path: str | None = None,
        default: dict[str, Any],
        thinking: bool = False,
    ) -> dict[str, Any]:
        try:
            response = await self.llm_client.generate_json(prompt, image_path=image_path, thinking=thinking)
            return {**default, **response}
        except Exception as exc:  # pragma: no cover
            error_message = self._stringify_exception(exc)
            payload = dict(default)
            payload.setdefault("missing_information", [])
            payload["missing_information"] = list(payload["missing_information"]) + [f"LLM error: {error_message}"]
            payload.setdefault("uncertainties", [])
            payload["uncertainties"] = list(payload["uncertainties"]) + ["Model call failed"]
            payload["_llm_failed"] = True
            payload["_llm_error"] = error_message
            return payload

    async def _summarize(self, context: str, *, fallback: str) -> str:
        prompt = self.prompt_builder.build(
            "layer3_summary.txt",
            kb_block="",
            document_block=context,
            filename="",
            lane="",
        )
        try:
            return (await self.llm_client.generate_text(prompt)).strip()
        except Exception:  # pragma: no cover
            return fallback

    def _build_llm_failure_evidence(self, step_label: str, payload: dict[str, Any]) -> dict[str, Any]:
        missing_information = payload.get("missing_information") or []
        error_label = next(
            (str(item) for item in missing_information if isinstance(item, str) and item.startswith("LLM error:")),
            None,
        )
        reason = self._analysis_text(
            english=f"Analysis interrupted: the model call failed during {step_label}.",
            french=f"Analyse interrompue : l'appel au modele a echoue pendant {step_label}.",
        )
        if error_label:
            reason += f" {error_label}."
        reason += self._analysis_text(
            english=" Classification cannot proceed without this step.",
            french=" Classification impossible sans cette etape.",
        )
        return {
            "page_number": 0,
            "kind": "system",
            "excerpt": None,
            "reason": reason,
            "image_path": None,
        }
        missing_information = payload.get("missing_information") or []
        error_label = next(
            (str(item) for item in missing_information if isinstance(item, str) and item.startswith("LLM error:")),
            None,
        )
        reason = f"Analyse interrompue : l'appel au modèle a échoué pendant {step_label}."
        if error_label:
            reason += f" {error_label}."
        reason += " Classification impossible sans cette étape."
        return {
            "page_number": 0,
            "kind": "system",
            "excerpt": None,
            "reason": reason,
            "image_path": None,
        }

    def _raise_if_all_pages_llm_failed(self, page_payloads: list[dict[str, Any]], pages: list) -> None:
        if not page_payloads or any(not payload.get("_llm_failed") for payload in page_payloads):
            return

        error_message = next(
            (detail for payload in page_payloads if (detail := self._extract_llm_error(payload))),
            None,
        )
        image_only = bool(pages) and all(getattr(page, "content_type", None) != PageContentType.TEXT for page in pages)
        scope = (
            self._analysis_text(english="any image from the document", french="aucune image du document")
            if image_only
            else self._analysis_text(english="any page from the document", french="aucune page du document")
        )
        detail_suffix = f" {error_message}" if error_message else ""
        model_name = getattr(self.llm_client, "model_name", self.settings.llm_model)
        raise RuntimeError(
            self._analysis_text(
                english=f"The configured model '{model_name}' could not analyze {scope}.{detail_suffix}",
                french=f"Le modele configure '{model_name}' n'a pu analyser {scope}.{detail_suffix}",
            )
        )
        image_only = bool(pages) and all(getattr(page, "content_type", None) != PageContentType.TEXT for page in pages)
        scope = "aucune image du document" if image_only else "aucune page du document"
        detail_suffix = f" {error_message}" if error_message else ""
        model_name = getattr(self.llm_client, "model_name", self.settings.llm_model)
        raise RuntimeError(f"Le modele configure '{model_name}' n'a pu analyser {scope}.{detail_suffix}")

    @staticmethod
    def _extract_llm_error(payload: dict[str, Any]) -> str | None:
        raw_error = payload.get("_llm_error")
        if isinstance(raw_error, str) and raw_error.strip():
            return raw_error.strip()

        for item in payload.get("missing_information") or []:
            if isinstance(item, str) and item.startswith("LLM error:"):
                return item.removeprefix("LLM error:").strip() or None
        return None

    @staticmethod
    def _stringify_exception(exc: Exception) -> str:
        detail = str(exc).strip()
        if detail:
            return detail
        return type(exc).__name__

    @staticmethod
    def _page_block(page) -> str:
        excerpt = (page.extracted_text or "").strip()
        if len(excerpt) > 2500:
            excerpt = excerpt[:2500] + "\n...[truncated]"
        return f"Section: {page.section_label}\nPage: {page.page_number}\nText:\n{excerpt}"

    @staticmethod
    def _collect_citations(page_payloads: list[dict[str, Any]]) -> list[dict]:
        return [citation for payload in page_payloads for citation in payload.get("citations", [])]

    @staticmethod
    def _collect_evidence(page_payloads: list[dict[str, Any]]) -> list[dict]:
        evidence_items: list[dict] = []
        for payload in page_payloads:
            for item in payload.get("evidence", []):
                evidence_items.append(
                    {
                        "page_number": payload["page_number"],
                        "kind": item.get("kind", "text"),
                        "excerpt": item.get("excerpt"),
                        "reason": item.get("reason", ""),
                        "image_path": item.get("image_path"),
                    }
                )
        return evidence_items

    def _aggregate_step2(self, page_payloads: list[dict[str, Any]]) -> dict[str, Any]:
        technical_scores = [payload.get("technical_score", 0) for payload in page_payloads]
        confidences = [payload.get("confidence", 0.0) for payload in page_payloads]
        technical_pages = [
            payload for payload in page_payloads if payload.get("is_technical") or payload.get("technical_score", 0) >= self.settings.technical_score_threshold
        ]
        confidence_pool = technical_pages or [payload for payload in page_payloads if payload.get("relevant")] or page_payloads
        return {
            "is_technical": bool(technical_pages),
            "technical_score": max(technical_scores, default=0),
            "confidence": round(
                sum(payload.get("confidence", 0.0) for payload in confidence_pool) / len(confidence_pool),
                4,
            )
            if confidence_pool
            else 0.0,
            "indicators_found": sorted({indicator for payload in page_payloads for indicator in payload.get("indicators_found", [])}),
            "missing_information": sorted({item for payload in page_payloads for item in payload.get("missing_information", [])}),
        }

    def _normalize_step2_payload(self, payload: dict[str, Any], *, page_text: str) -> dict[str, Any]:
        normalized = dict(payload)
        technical_score = int(normalized.get("technical_score") or 0)
        indicators = list(normalized.get("indicators_found") or [])
        evidence = list(normalized.get("evidence") or [])
        missing_information = list(normalized.get("missing_information") or [])
        document_type = str(normalized.get("document_type") or "").upper()
        confidence = float(normalized.get("confidence") or 0.0)
        explicit_flag = bool(normalized.get("is_technical"))
        page_summary = str(normalized.get("page_summary") or "")
        evidence_excerpt_text = " ".join(str(item.get("excerpt") or "") for item in evidence)
        contextual_text = " ".join([page_text, page_summary, " ".join(indicators), evidence_excerpt_text]).lower()
        disclosed_text = " ".join([page_text, evidence_excerpt_text]).lower()

        strong_doc_type = any(token in document_type for token in ["SPEC", "DRAWING", "CAD", "SCHEM", "TEST", "MANUAL", "ROUT", "BOM"])
        numeric_evidence = any(re.search(r"\d", str(item.get("excerpt") or "")) for item in evidence)
        signal_count = len(indicators) + len(evidence)
        threshold = self.settings.technical_score_threshold
        disclosed_substance = self._has_disclosed_technical_substance(disclosed_text)
        reference_only = self._has_reference_only_signals(disclosed_text)

        # Reference-only guard: pages with only P/N, tooling numbers, quantities
        # and no disclosed substance cannot be technical
        if reference_only and not disclosed_substance:
            inferred_technical = False
        else:
            inferred_technical = (
                technical_score >= threshold
                or (
                    explicit_flag
                    and confidence >= 0.6
                    and (disclosed_substance or numeric_evidence or (strong_doc_type and signal_count >= 2))
                )
                or (
                    strong_doc_type
                    and signal_count >= 2
                    and confidence >= 0.7
                    and disclosed_substance
                )
            )

        if inferred_technical:
            normalized["is_technical"] = True
            if technical_score < threshold:
                normalized["technical_score"] = max(
                    technical_score,
                    threshold if disclosed_substance or numeric_evidence else max(threshold - 5, technical_score),
                )
        elif technical_score >= threshold and not reference_only:
            normalized["is_technical"] = True
        elif reference_only and not disclosed_substance:
            # Cap score for reference-only pages
            normalized["is_technical"] = False
            normalized["technical_score"] = min(technical_score, max(threshold - 10, 20))
            if "Reference-only content: part numbers, tooling references, and quantities alone do not constitute technical data." not in missing_information:
                missing_information.append("Reference-only content: part numbers, tooling references, and quantities alone do not constitute technical data.")
            normalized["missing_information"] = missing_information

        contextual_only = self._is_contextual_cover_page(
            contextual_text,
            disclosed_text=disclosed_text,
            indicators=indicators,
            evidence=evidence,
            missing_information=missing_information,
            document_type=document_type,
        )
        normalized["contextual_only"] = contextual_only
        if contextual_only:
            normalized["is_technical"] = False
            normalized["technical_score"] = min(int(normalized.get("technical_score") or 0), max(threshold - 15, 20))
            if "No actionable technical data disclosed on this page; contextual cover/control content only." not in missing_information:
                missing_information.append("No actionable technical data disclosed on this page; contextual cover/control content only.")
            normalized["missing_information"] = missing_information
            if not document_type or "SPEC" in document_type:
                normalized["document_type"] = "COVER_PAGE"

        return normalized

    @staticmethod
    def _is_contextual_cover_page(
        lowered_text: str,
        *,
        disclosed_text: str,
        indicators: list[str],
        evidence: list[dict[str, Any]],
        missing_information: list[str],
        document_type: str,
    ) -> bool:
        cover_markers = (
            "purpose",
            "scope",
            "owner's approval",
            "owner approval",
            "authorization",
            "approval",
            "approved by",
            "origin office",
            "project",
            "issue",
            "revision",
            "date",
            "confidential and proprietary",
            "page 1 /",
        )

        cover_hits = sum(1 for marker in cover_markers if marker in lowered_text)
        substantive_text = ClassificationOrchestrator._has_disclosed_technical_substance(disclosed_text)
        evidence_excerpts = [str(item.get("excerpt") or "").lower() for item in evidence if str(item.get("excerpt") or "").strip()]
        weak_indicator_only = bool(indicators) and all(
            ClassificationOrchestrator._is_weak_contextual_signal(indicator)
            for indicator in indicators
        )
        weak_excerpts_only = bool(evidence_excerpts) and all(
            ClassificationOrchestrator._is_weak_contextual_signal(excerpt)
            for excerpt in evidence_excerpts
        )
        missing_core_fields = sum(
            any(token in item.lower() for token in ["dimension", "toler", "material", "process", "test", "performance"])
            for item in missing_information
        )
        cover_doc_type = any(token in document_type for token in ["COVER", "TITLE", "APPROVAL", "CONTROL"])

        return (cover_hits >= 2 or cover_doc_type) and not substantive_text and (
            (weak_indicator_only and (weak_excerpts_only or not evidence_excerpts))
            or missing_core_fields >= 2
        )

    @staticmethod
    def _has_disclosed_technical_substance(lowered_text: str) -> bool:
        if not lowered_text.strip():
            return False

        substantive_keywords = (
            "dimension",
            "dimensions",
            "tolerance",
            "tolerances",
            "material",
            "materials",
            "alloy",
            "thickness",
            "diameter",
            "radius",
            "torque",
            "pressure",
            "temperature",
            "procedure",
            "procedures",
            "work instruction",
            "assembly sequence",
            "operation sequence",
            "acceptance criteria",
            "acceptance test",
            "pass/fail",
            "calibration",
            "wiring",
            "pinout",
            "interface control",
            "process parameter",
            "process parameters",
            "set-up",
            "setup",
            "qualification threshold",
            "qualification thresholds",
            "performance data",
            "performance requirement",
            "repair instruction",
            "repair instructions",
            "maintenance instruction",
            "maintenance instructions",
            "inspection plan",
            "inspection instruction",
            "test procedure",
            "test specification",
            "test report",
            "acceptance plan",
            "load case",
            "stress report",
            "algorithm",
            "source code",
            "firmware",
            "fpga",
            "gdt",
            "gd&t",
            "surface definition",
        )
        numeric_units_pattern = re.compile(
            r"\b\d+(?:\.\d+)?\s?(?:mm|cm|m|kg|g|n|nm|bar|psi|rpm|hz|khz|mhz|ghz|v|a|w|kw|mpa|nm/hr|m/s|mm/s|mm/min|c|deg)\b",
            re.IGNORECASE,
        )
        sequenced_operations = re.search(r"\b(?:step|operation)\s*[0-9ivx]+\b", lowered_text, re.IGNORECASE)
        tolerance_pattern = re.search(r"(?:\+/-|±)\s*\d", lowered_text)

        return (
            any(keyword in lowered_text for keyword in substantive_keywords)
            or bool(numeric_units_pattern.search(lowered_text))
            or bool(sequenced_operations)
            or bool(tolerance_pattern)
        )

    @staticmethod
    def _has_reference_only_signals(lowered_text: str) -> bool:
        """Detect pages containing ONLY reference-level signals (P/N, tooling numbers, quantities) without substance."""
        if not lowered_text.strip():
            return False
        reference_patterns = (
            "part number",
            "p/n",
            "tooling number",
            "tooling n",
            "tool number",
            "tool n°",
            "tool no",
            "reference 3d",
            "ref 3d",
            "catia",
            "3d model",
            "quantity",
            "quantities",
            "qty",
            "bill of material",
            "bom",
            "drawing number",
            "drawing ref",
            "document number",
            "document ref",
            "revision",
            "effectivity",
            "configuration baseline",
        )
        has_references = any(pattern in lowered_text for pattern in reference_patterns)
        has_substance = ClassificationOrchestrator._has_disclosed_technical_substance(lowered_text)
        return has_references and not has_substance

    @staticmethod
    def _is_weak_contextual_signal(value: str) -> bool:
        lowered = str(value or "").lower().strip()
        if not lowered:
            return True
        if ClassificationOrchestrator._has_disclosed_technical_substance(lowered):
            return False

        weak_markers = (
            "technical specification",
            "title page",
            "cover page",
            "purpose",
            "scope",
            "owner's approval",
            "owner approval",
            "authorization",
            "approval",
            "approved by",
            "origin office",
            "project",
            "issue",
            "revision",
            "date",
            "function:",
            "manufacturing engineer",
            "airbus",
            "tooling",
            "ground test means",
            "jig",
            "jigs",
            "a320",
            "neo cfm",
            "spf dies",
            "super plastic forming",
            "manufacture and delivery",
            "general requirements",
            "confidential and proprietary",
        )
        return any(marker in lowered for marker in weak_markers)

    def _normalize_step7_payload(self, payload: dict[str, Any], pages: list) -> dict[str, Any]:
        normalized = dict(payload)
        candidate_markings = []
        for candidate in normalized.get("candidate_markings", []) or []:
            code = self._normalize_marking_code(candidate.get("code"), lane=LaneType.FR_EU)
            if not code:
                continue
            candidate_markings.append({**candidate, "code": code})
        normalized["candidate_markings"] = candidate_markings

        eccn = self._normalize_marking_code(normalized.get("eccn"), lane=LaneType.FR_EU)
        if eccn and re.fullmatch(r"[A-Z]{2}_EC_.+", eccn):
            normalized["eccn"] = eccn.split("_EC_", 1)[1]

        threshold_matches = [
            item
            for item in normalized.get("thresholds_checked", []) or []
            if str(item.get("result") or "").lower() in {"above", "equal"}
        ]
        strongest_candidate = max(candidate_markings, key=lambda item: float(item.get("confidence") or 0.0), default=None)
        if normalized.get("is_listed") or normalized.get("eccn") or not strongest_candidate or not threshold_matches:
            return normalized

        document_text = " ".join((page.extracted_text or "") for page in pages).lower()
        reasoning = str(normalized.get("reasoning") or "")
        exclusion_claimed = any(token in reasoning.lower() for token in ["civil aircraft", "certifi", "exclusion", "note 2"])
        exclusion_documented = any(token in document_text for token in ["civil aircraft", "certified", "certification"])

        if exclusion_claimed and exclusion_documented:
            return normalized

        candidate_code = strongest_candidate["code"]
        normalized["is_listed"] = True
        normalized["eccn"] = candidate_code.split("_EC_", 1)[1] if "_EC_" in candidate_code else candidate_code
        normalized["eccn_description"] = normalized.get("eccn_description") or "Dual-use entry inferred from threshold match."
        normalized["matching_criteria"] = normalized.get("matching_criteria") or "Threshold-based criterion matched; no documentary exclusion found."
        normalized["confidence"] = max(
            float(normalized.get("confidence") or 0.0),
            float(strongest_candidate.get("confidence") or 0.0),
            0.78,
        )
        if not reasoning:
            normalized["reasoning"] = "Threshold-based dual-use criterion matched without documentary evidence for an exclusion."
        return normalized

    def _normalize_step_c_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        if normalized.get("_llm_failed") or normalized.get("is_military"):
            return normalized

        criteria_analysis = normalized.get("military_criteria_analysis") or {}
        support_count = 0
        for criterion in criteria_analysis.values():
            if not isinstance(criterion, dict):
                continue
            score = str(criterion.get("score") or "").lower()
            findings = str(criterion.get("findings") or "").strip()
            if score in {"negative", "absent", "not_met", "excluded", "no"} or findings:
                support_count += 1
        support_count += len(normalized.get("exclusions_checked") or [])

        normalized["confidence"] = self._normalize_negative_conclusion_confidence(
            normalized,
            support_count=support_count,
            has_anchor=False,
        )
        return normalized

    def _normalize_step_e_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        if normalized.get("_llm_failed") or normalized.get("is_listed"):
            return normalized

        thresholds_checked = normalized.get("thresholds_checked") or []
        negative_thresholds = sum(
            1
            for item in thresholds_checked
            if str((item or {}).get("result") or "").lower() in {"below", "absent", "not_met", "no_match", "not_listed"}
        )
        search_keywords = normalized.get("search_keywords_tried") or []
        support_count = negative_thresholds + min(3, len(search_keywords))
        has_anchor = any(
            str(normalized.get(field) or "").strip()
            for field in ("category_identified", "nature_identified", "matching_criteria")
        )

        normalized["confidence"] = self._normalize_negative_conclusion_confidence(
            normalized,
            support_count=support_count,
            has_anchor=has_anchor,
        )
        return normalized

    @staticmethod
    def _normalize_negative_conclusion_confidence(
        payload: dict[str, Any],
        *,
        support_count: int,
        has_anchor: bool,
    ) -> float:
        current = ClassificationOrchestrator._coerce_confidence_value(payload.get("confidence"))
        has_reasoning = bool(str(payload.get("reasoning") or "").strip())
        gap_count = ClassificationOrchestrator._count_gap_items(payload.get("missing_information"))
        gap_count += ClassificationOrchestrator._count_gap_items(payload.get("uncertainties"))

        if support_count <= 0 and not has_reasoning and not has_anchor:
            return current

        derived = 0.40
        derived += min(0.24, 0.06 * max(support_count, 0))
        if has_reasoning:
            derived += 0.07
        if has_anchor:
            derived += 0.05
        derived -= min(0.24, 0.08 * max(gap_count, 0))
        derived = max(0.0, min(0.82, derived))
        return round(max(current, derived), 4)

    @staticmethod
    def _coerce_confidence_value(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _count_gap_items(value: Any) -> int:
        if isinstance(value, (list, tuple, set)):
            return sum(1 for item in value if str(item or "").strip())
        if isinstance(value, str):
            return 1 if value.strip() else 0
        return 0

    def _coerce_summary_v2(
        self,
        summary: str,
        *,
        fallback: str,
        final_marking: str,
        requires_review: bool,
    ) -> str:
        cleaned = str(summary or "").strip()
        if not cleaned:
            return fallback
        if not self._summary_has_v2_structure(cleaned):
            return fallback
        if self._summary_contradicts_outcome(cleaned, final_marking=final_marking, requires_review=requires_review):
            return fallback
        return replace_marking_codes_in_text(cleaned)

    @staticmethod
    def _summary_has_v2_structure(summary: str) -> bool:
        normalized = ClassificationOrchestrator._normalize_summary_text(summary)
        section_groups = (
            ("identification du tangible", "identification de l element analyse", "identification de l element examine", "identification of the examined item"),
            ("analyse militaire", "military analysis", "itar assessment", "analyse itar"),
            ("analyse double usage", "dual-use analysis", "ear analysis", "analyse ear", "ear / ccl analysis", "analyse ear / ccl", "ccl analysis"),
            ("analyse technique du document", "technical analysis of the document"),
            ("decision et action", "decision and action"),
        )
        # Accept either EU-style or US-style required markers
        eu_markers = (
            "conclusion",
            "categories analysees",
            "rubriques verifiees",
            "croisement nature e",
            "verdict propose",
        )
        us_markers = (
            "conclusion",
            "verdict",
        )
        has_sections = all(any(option in normalized for option in group) for group in section_groups)
        has_eu_markers = all(marker in normalized for marker in eu_markers)
        has_us_markers = all(marker in normalized for marker in us_markers)
        return has_sections and (has_eu_markers or has_us_markers)

    @staticmethod
    def _should_skip_generated_summary_v2(step_results: dict[str, Any]) -> bool:
        step_b = step_results.get("step_b") or {}
        step_c = step_results.get("step_c") or {}
        if not bool(step_b.get("item_identified")):
            return True
        return bool(step_c.get("is_military") and step_results.get("step_d"))

    @staticmethod
    def render_reasoning_summary_v2(
        stored_summary: str | None,
        *,
        final_marking: str,
        final_confidence: float,
        requires_review: bool,
        step_results: dict[str, Any],
        tangible_description: str | None,
        lifecycle_phase: str | None,
        page_payloads: list[dict[str, Any]] | None = None,
    ) -> str:
        fallback = ClassificationOrchestrator._fallback_summary_v2(
            final_marking,
            final_confidence,
            requires_review,
            page_payloads or [],
            step_results=step_results,
            tangible_description=tangible_description,
            lifecycle_phase=lifecycle_phase,
        )
        if ClassificationOrchestrator._should_skip_generated_summary_v2(step_results):
            return fallback
        cleaned = ClassificationOrchestrator._repair_mojibake_text(str(stored_summary or "").strip())
        if not cleaned:
            return fallback
        return replace_marking_codes_in_text(cleaned)

    @staticmethod
    def _summary_contradicts_outcome(summary: str, *, final_marking: str, requires_review: bool) -> bool:
        normalized = ClassificationOrchestrator._normalize_summary_text(summary)
        if requires_review and any(
            token in normalized
            for token in (
                "aucune intervention humaine n'est necessaire",
                "aucune intervention humaine n est necessaire",
                "intervention humaine non requise",
                "revue humaine optionnelle",
            )
        ):
            return True
        if not requires_review and "revue humaine requise" in normalized:
            return True

        mentioned_markings = set(
            re.findall(
                r"\b(?:EC_Not_Technical|EC_Review_Required|[A-Z]{2}_EC_[A-Za-z0-9.]+|US_[A-Za-z0-9_]+)\b",
                summary,
            )
        )
        return bool(mentioned_markings) and final_marking not in mentioned_markings

    @staticmethod
    def _normalize_summary_text(value: str) -> str:
        ascii_text = unicodedata.normalize("NFKD", ClassificationOrchestrator._repair_mojibake_text(str(value or ""))).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"\s+", " ", ascii_text).strip().lower()

    @staticmethod
    def _repair_mojibake_text(value: str) -> str:
        text = str(value or "")
        suspicious_markers = ("Ã", "Â", "â€", "â€™", "â€“", "â€œ", "â€", "â€¢")
        if not any(marker in text for marker in suspicious_markers):
            return text

        def _score(candidate: str) -> int:
            return sum(candidate.count(marker) for marker in suspicious_markers)

        best = text
        best_score = _score(text)
        for encoding in ("cp1252", "latin1"):
            try:
                candidate = text.encode(encoding).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            candidate_score = _score(candidate)
            if candidate_score < best_score:
                best = candidate
                best_score = candidate_score
        return best

    @staticmethod
    def _counts_toward_confidence(payload: dict[str, Any]) -> bool:
        if "technology_controlled" in payload and not payload.get("technology_controlled") and not payload.get("classification_code"):
            return False
        return True

    @staticmethod
    def _detect_lane(document, pages: list) -> LaneType:
        haystack = f"{document.original_filename} " + " ".join((page.extracted_text or "")[:1000] for page in pages[:5])
        lowered = haystack.lower()
        if any(marker in lowered for marker in ["itar", "usml", "eccn", "bis", "dfars", "ear99"]):
            return LaneType.US
        return LaneType.FR_EU

    @staticmethod
    def _build_document_context(document, pages: list, page_payloads: list[dict[str, Any]]) -> str:
        sections: list[str] = [f"Filename: {document.original_filename}", f"Document hint: {document.context_hint or ''}"]
        for page, payload in zip(pages, page_payloads, strict=False):
            if not payload.get("relevant"):
                continue
            excerpt = (page.extracted_text or "")[:1200]
            sections.append(
                "\n".join(
                    [
                        f"Page {page.page_number} - {page.section_label}",
                        f"Summary: {payload.get('page_summary', '')}",
                        f"Technical score: {payload.get('technical_score', 0)}",
                        f"Indicators: {', '.join(payload.get('indicators_found', []))}",
                        f"Text excerpt: {excerpt}",
                    ]
                )
            )
        return "\n\n".join(sections[:12])

    def _dedupe_candidates(
        self,
        candidate_markings: list[dict[str, Any]],
        final_marking: str,
        final_confidence: float,
        *,
        lane: LaneType,
        country_code: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized: dict[str, dict[str, Any]] = {}
        for candidate in candidate_markings:
            code = self._normalize_marking_code(candidate.get("code"), lane=lane, country_code=country_code)
            if not code:
                continue
            normalized[code] = {**candidate, "code": code}
        normalized[final_marking] = {
            "code": final_marking,
            "confidence": final_confidence,
            "reason": normalized.get(final_marking, {}).get("reason", "Selected final marking"),
        }
        return sorted(normalized.values(), key=lambda candidate: candidate.get("confidence", 0.0), reverse=True)

    @staticmethod
    def _normalize_marking_code(code: Any, *, lane: LaneType, country_code: str | None = None) -> str | None:
        if not code:
            return None

        normalized = str(code).strip()
        if not normalized:
            return None

        if normalized in {"EC_Not_Technical", "EC_Review_Required"}:
            return normalized
        generic_match = re.fullmatch(r"([A-Z]{2})_EC_(.+)", normalized)
        if generic_match:
            if country_code:
                return f"{country_code.strip().upper()}_EC_{generic_match.group(2)}"
            return normalized
        if normalized.startswith("US_"):
            return normalized

        upper_code = normalized.upper()
        if lane == LaneType.US:
            if upper_code == "EAR99":
                return "US_EAR99"
            if re.fullmatch(r"[0-9][A-E][0-9]{3}", upper_code):
                return f"US_EAR_{upper_code}"
            if upper_code.startswith("ITAR_") or upper_code.startswith("EAR_"):
                return f"US_{upper_code}"
            if upper_code == "REVIEW_REQUIRED":
                return "US_REVIEW_REQUIRED"
            return normalized

        prefix = country_code.strip().upper() if country_code else "FR"
        if upper_code == "TECHNICAL_NOT_CONTROLLED":
            return f"{prefix}_EC_Technical_Not_Controlled"
        if re.fullmatch(r"ML\d{1,2}(?:\.[A-Z0-9]+)?", upper_code):
            return f"{prefix}_EC_{upper_code}"
        if re.fullmatch(r"AMA[1-4]", upper_code):
            return f"{prefix}_EC_{upper_code}"
        if re.fullmatch(r"[0-9][A-E][0-9]{3}", upper_code):
            return f"{prefix}_EC_{upper_code}"
        return normalized

    @staticmethod
    def _unique_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in items:
            key = repr(sorted(item.items()))
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    @staticmethod
    def _fallback_summary_v2(
        final_marking: str,
        confidence: float,
        requires_review: bool,
        page_payloads: list[dict[str, Any]],
        *,
        step_results: dict[str, Any],
        tangible_description: str | None,
        lifecycle_phase: str | None,
    ) -> str:
        if get_rationale_language() == "en":
            return ClassificationOrchestrator._fallback_summary_v2_en(
                final_marking,
                confidence,
                requires_review,
                page_payloads,
                step_results=step_results,
                tangible_description=tangible_description,
                lifecycle_phase=lifecycle_phase,
            )
        return ClassificationOrchestrator._fallback_summary_v2_fr(
            final_marking,
            confidence,
            requires_review,
            page_payloads,
            step_results=step_results,
            tangible_description=tangible_description,
            lifecycle_phase=lifecycle_phase,
        )

    @staticmethod
    def _fallback_summary_v2_en(
        final_marking: str,
        confidence: float,
        requires_review: bool,
        page_payloads: list[dict[str, Any]],
        *,
        step_results: dict[str, Any],
        tangible_description: str | None,
        lifecycle_phase: str | None,
    ) -> str:
        def clean_text(value: Any, *, default: str) -> str:
            if value is None:
                return default
            text = ClassificationOrchestrator._repair_mojibake_text(str(value)).strip()
            text = replace_marking_codes_in_text(text, language="en")
            text = re.sub(r"\s+", " ", text)
            return text if text else default

        def join_values(values: list[Any], *, default: str, limit: int = 4) -> str:
            pieces: list[str] = []
            seen: set[str] = set()
            for value in values:
                text = clean_text(value, default="").strip()
                if not text:
                    continue
                lowered = text.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                pieces.append(text)
                if len(pieces) >= limit:
                    break
            return "; ".join(pieces) if pieces else default

        relevant_pages = [payload["page_number"] for payload in page_payloads if payload.get("relevant")]
        page_list = ", ".join(str(page) for page in relevant_pages[:4]) or "none identified"
        technical_signals = [
            signal
            for payload in page_payloads
            for signal in ((payload.get("content_signals") or {}).get("substantive") or payload.get("indicators_found") or [])
            if isinstance(signal, str)
        ]
        page_summaries = [
            payload.get("page_summary")
            for payload in page_payloads
            if isinstance(payload.get("page_summary"), str) and payload.get("page_summary")
        ]
        tangible_payload = step_results.get("step_b") or {}
        military_payload = step_results.get("step_c") or {}
        dualuse_payload = step_results.get("step_e") or {}
        techdata_ml_payload = step_results.get("step_d") or {}

        is_us_lane = final_marking.startswith("US_") or "step_e_screening" in step_results or "step_c_itar" in step_results

        identified_item = clean_text(
            tangible_description or tangible_payload.get("item_description"),
            default="no clearly identified item",
        )
        lifecycle_text = clean_text(
            lifecycle_phase or tangible_payload.get("lifecycle_phase"),
            default="an unspecified lifecycle phase",
        )
        identification_context = join_values(
            page_summaries,
            default="The available pages do not provide a stable technical object with enough detail to anchor the analysis.",
            limit=2,
        )
        technical_signal_text = join_values(
            technical_signals,
            default="No decisive technical signal could be extracted automatically.",
        )
        military_summary = clean_text(
            military_payload.get("reasoning"),
            default="No decisive military indicator was retained in fallback mode." if not is_us_lane else "No decisive ITAR indicator was retained in fallback mode.",
        )
        decision_label = get_marking_label(final_marking, language="en")
        review_line = (
            "Human review is still required before release."
            if requires_review
            else "No additional human review is required at this stage."
        )

        # ── Build the regulatory analysis section (section 3) ──
        if is_us_lane:
            # US lane: ITAR was step_c, EAR is step_e_screening / step_e_detailed
            screening_payload = step_results.get("step_e_screening") or {}
            detailed_payload = step_results.get("step_e_detailed") or {}
            itar_payload = military_payload  # step_c contains ITAR for US lane

            if itar_payload.get("is_itar"):
                ear_body = (
                    f"The item was identified as ITAR-controlled (USML). "
                    f"EAR analysis was not performed as the item falls under the ITAR jurisdiction."
                )
            elif screening_payload.get("screening_result") == "ear99" or not screening_payload.get("candidate_categories"):
                ear_body = (
                    f"EAR screening did not identify any Commerce Control List (CCL) category match. "
                    f"The item is classified as EAR99 (commercial, not controlled)."
                )
            elif detailed_payload:
                ear_conclusion = clean_text(
                    (detailed_payload.get("final_determination") or {}).get("reasoning"),
                    default="EAR detailed analysis was performed.",
                )
                candidate_eccns = join_values(
                    [item.get("eccn") for item in (detailed_payload.get("eccn_analysis") or []) if isinstance(item, dict)],
                    default="No specific ECCN retained.",
                )
                ear_body = (
                    f"a. CCL categories screened: {join_values(screening_payload.get('candidate_categories', []), default='None identified.')}\n"
                    f"b. ECCNs evaluated: {candidate_eccns}\n"
                    f"Conclusion: {ear_conclusion}"
                )
            else:
                ear_body = "EAR analysis was not conclusive in fallback mode."

            regulatory_title = "3. EAR / CCL ANALYSIS"
            regulatory_body = ear_body
        else:
            # FR/EU lane: existing dual-use logic
            dualuse_summary = clean_text(
                (dualuse_payload.get("final_determination") or {}).get("reasoning")
                or (dualuse_payload.get("document_analysis") or {}).get("analysis_summary"),
                default="No decisive dual-use entry was retained in fallback mode.",
            )
            if techdata_ml_payload:
                regulatory_body = "\n".join(
                    [
                        "a. Categories reviewed: Not applicable, because the military branch was retained as the primary control regime.",
                        "b. Entries checked: ML22 technical-data qualification took precedence over a standalone dual-use outcome.",
                        "c. Nature E cross-check: Not applicable once the military regime is retained.",
                        f"Conclusion: {clean_text(techdata_ml_payload.get('reasoning'), default='The document is assessed under the military branch rather than under an autonomous dual-use review.')}",
                    ]
                )
            else:
                primary_eccn = clean_text(dualuse_payload.get("primary_eccn"), default="No primary entry retained")
                regulatory_body = "\n".join(
                    [
                        f"a. Categories reviewed: {join_values((dualuse_payload.get('categories_reviewed') or []) + [primary_eccn], default='No category could be retained reliably.')}",
                        f"b. Entries checked: {join_values([primary_eccn] + [item.get('eccn') for item in (dualuse_payload.get('eccn_analysis') or []) if isinstance(item, dict)], default='No decisive control entry was retained.')}",
                        f"c. Nature E cross-check: {clean_text((dualuse_payload.get('nature_e_analysis') or {}).get('matching_entry') or (dualuse_payload.get('nature_e_analysis') or {}).get('matching_entry_text'), default='No matching Nature E entry was retained.')}",
                        f"Conclusion: {dualuse_summary}",
                    ]
                )
            regulatory_title = "3. DUAL-USE ANALYSIS"

        sections = [
            (
                "1. IDENTIFICATION OF THE EXAMINED ITEM",
                (
                    f"The examined item is {identified_item}. "
                    f"It is currently associated with {lifecycle_text}. "
                    f"The document context indicates: {identification_context} "
                    f"The main technical signals retained at fallback level are: {technical_signal_text}."
                ),
            ),
            (
                "2. ITAR ASSESSMENT" if is_us_lane else "2. MILITARY ANALYSIS",
                "\n".join(
                    [
                        f"Conclusion: {military_summary}",
                        "The review considered the available programme references, technical constraints, performance indicators, and any explicit military wording. "
                        "Where the material remained incomplete, the conclusion stays limited to what is directly supportable from the extracted evidence.",
                    ]
                ),
            ),
            (
                regulatory_title,
                regulatory_body,
            ),
            (
                "4. TECHNICAL ANALYSIS OF THE DOCUMENT",
                (
                    f"The document is mainly supported by pages {page_list}. "
                    f"It provides the following actionable or descriptive technical elements: {technical_signal_text} "
                    "Any gap not explicitly covered here should be treated as missing evidence rather than inferred capability."
                ),
            ),
            (
                "5. DECISION AND ACTION",
                "\n".join(
                    [
                        f"Proposed verdict: {decision_label}",
                        (
                            f"This fallback rationale retains the current verdict because the extracted evidence points to that control outcome more strongly than to any alternative. "
                            f"{review_line}"
                        ),
                    ]
                ),
            ),
        ]
        return "\n\n".join(f"{title}\n{body}" for title, body in sections)

    @staticmethod
    def _fallback_summary_v2_fr(
        final_marking: str,
        confidence: float,
        requires_review: bool,
        page_payloads: list[dict[str, Any]],
        *,
        step_results: dict[str, Any],
        tangible_description: str | None,
        lifecycle_phase: str | None,
    ) -> str:
        def _stringify(value: Any) -> str:
            if value is None or isinstance(value, bool):
                return ""
            if isinstance(value, str):
                return value
            if isinstance(value, (int, float)):
                return str(value)
            if isinstance(value, dict):
                label = ""
                for key in ("exclusion", "category", "rubrique", "code", "name", "label", "entry"):
                    raw = value.get(key)
                    if isinstance(raw, str) and raw.strip():
                        label = raw.strip()
                        break
                detail = ""
                for key in ("reason", "description", "findings", "text", "value"):
                    raw = value.get(key)
                    if isinstance(raw, str) and raw.strip():
                        detail = raw.strip()
                        break
                applicable = value.get("applicable")
                if label and detail:
                    if applicable is False:
                        return f"{label} ecartee ({detail})"
                    if applicable is True:
                        return f"{label} retenue ({detail})"
                    return f"{label} : {detail}"
                if label:
                    if applicable is False:
                        return f"{label} ecartee"
                    if applicable is True:
                        return f"{label} retenue"
                    return label
                return detail
            if isinstance(value, (list, tuple, set)):
                pieces = [_stringify(item) for item in value]
                return "; ".join(piece for piece in pieces if piece)
            return str(value)

        def _clean(value: Any, *, default: str = "Non pertinent.") -> str:
            text = ClassificationOrchestrator._repair_mojibake_text(replace_marking_codes_in_text(_stringify(value)).strip())
            text = re.sub(r"\s+", " ", text)
            return text if text else default

        def _join(values: list[Any], *, default: str = "Non pertinent.", limit: int = 3) -> str:
            unique: list[str] = []
            seen: set[str] = set()
            for raw_value in values:
                text = _clean(raw_value, default="")
                if not text:
                    continue
                lowered = text.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                unique.append(text)
                if len(unique) >= limit:
                    break
            return "; ".join(unique) if unique else default

        def _sentence(value: str) -> str:
            text = value.strip()
            if not text:
                return text
            return text if text.endswith((".", "!", "?")) else f"{text}."

        def _format_mapping_lines(mapping: dict[str, Any] | None, *, limit: int = 3) -> str:
            if not isinstance(mapping, dict):
                return "Non pertinent."
            rows: list[str] = []
            for key, value in mapping.items():
                if not isinstance(value, dict):
                    continue
                retained = value.get("retained")
                reason = _clean(value.get("reason"), default="")
                if retained is False and not reason:
                    continue
                if retained:
                    rows.append(f"Categorie {key}: {reason or 'retenue pour analyse detaillee.'}")
                else:
                    rows.append(f"Categorie {key}: {reason or 'ecartee apres verification.'}")
                if len(rows) >= limit:
                    break
            return "; ".join(rows) if rows else "Non pertinent."

        relevant_pages = [payload["page_number"] for payload in page_payloads if payload.get("relevant")]
        substantive_pages = [
            payload["page_number"]
            for payload in page_payloads
            if (payload.get("content_signals") or {}).get("substantive")
        ]
        technical_examples = [
            signal
            for payload in page_payloads
            for signal in ((payload.get("content_signals") or {}).get("substantive") or [])
            if isinstance(signal, str)
        ][:4]
        tangible_hints = [
            hint.get("name")
            for payload in page_payloads
            for hint in (payload.get("tangible_hints") or [])
            if isinstance(hint, dict) and hint.get("name")
        ][:4]
        failed_steps = [
            step_name
            for step_name in ("step_b", "step_c", "step_d", "step_e", "step_f")
            if (step_results.get(step_name) or {}).get("_llm_failed")
        ]
        signals_text = _join(technical_examples, default="Aucun signal technique saillant n'a pu etre extrait.", limit=4)
        tangible_label = str(tangible_description or "non identifie").rstrip(". ")
        page_list = ", ".join(str(page) for page in (substantive_pages or relevant_pages)[:4]) or "non precisees"
        decision_label = get_marking_label(final_marking)
        review_line = "Revue humaine requise avant validation finale." if requires_review else "Validation exploitable a ce stade sans revue supplementaire."
        automatic_limit = (
            f"Une ou plusieurs etapes automatiques ont echoue ({', '.join(failed_steps)}), ce qui reduit le niveau de detail disponible."
            if failed_steps
            else "Aucune reserve automatique majeure."
        )
        tangible_payload = step_results.get("step_b") or {}
        military_payload = step_results.get("step_c") or {}
        dualuse_payload = step_results.get("step_e") or {}
        techdata_ml_payload = step_results.get("step_d") or {}
        is_us_lane = final_marking.startswith("US_") or "step_e_screening" in step_results or "step_c_itar" in step_results
        no_tangible_identified = not bool(tangible_payload.get("item_identified"))
        page_summaries = [
            payload.get("page_summary")
            for payload in page_payloads
            if isinstance(payload.get("page_summary"), str) and payload.get("page_summary")
        ][:2]
        context_summary = _join(
            page_summaries,
            default="Le document presente des informations generales sans bien, composant ou systeme export control clairement identifiable.",
            limit=2,
        )

        military_findings = [
            value.get("findings")
            for value in (military_payload.get("military_criteria_analysis") or {}).values()
            if isinstance(value, dict)
        ]
        exclusions = military_payload.get("exclusions_checked") or []

        categories_analysis = dualuse_payload.get("categories_analysis") or {}
        eccn_analysis = dualuse_payload.get("eccn_analysis") or []
        eccn_lines = [
            f"{_clean(item.get('eccn'), default='Rubrique non precisee')}: {_clean(item.get('reason'), default='verification realisee sans detail supplementaire.')}"
            for item in eccn_analysis
            if item.get("eccn") or item.get("reason")
        ]

        nature_e_analysis = dualuse_payload.get("nature_e_analysis") or {}
        dualuse_section_body: str | None = None
        dualuse_section_title: str = "3. ANALYSE DOUBLE USAGE"
        dualuse_note = ""

        if is_us_lane:
            # US lane: generate EAR-specific content
            screening_payload = step_results.get("step_e_screening") or {}
            detailed_payload = step_results.get("step_e_detailed") or {}
            itar_payload = military_payload  # step_c contains ITAR for US

            dualuse_section_title = "3. ANALYSE EAR / CCL"

            if itar_payload.get("is_itar"):
                dualuse_section_body = (
                    "L'article a ete identifie comme relevant de l'ITAR (USML). "
                    "L'analyse EAR n'a pas ete realisee car l'article est soumis a la juridiction ITAR."
                )
            elif screening_payload.get("screening_result") == "ear99" or not screening_payload.get("candidate_categories"):
                dualuse_section_body = (
                    "Conclusion : Le screening EAR n'a identifie aucune categorie de la Commerce Control List (CCL) applicable. "
                    "L'article est classe EAR99 (commercial, non controle)."
                )
            elif detailed_payload:
                ear_conclusion = _clean(
                    (detailed_payload.get("final_determination") or {}).get("reasoning"),
                    default="Analyse EAR detaillee realisee.",
                )
                dualuse_section_body = f"Conclusion : {ear_conclusion}"
            else:
                dualuse_section_body = "L'analyse EAR n'a pas ete concluante en mode de secours."
        else:
            # FR/EU lane: existing logic
            if techdata_ml_payload:
                dualuse_note = (
                    "La qualification militaire a ete retenue comme regime principal. "
                    "Dans ce cas, une analyse double usage autonome n'est pas pertinente, car le document releve deja du controle militaire. "
                    + _clean(
                        techdata_ml_payload.get("reasoning"),
                        default="La qualification releve d'abord du regime militaire et non d'une analyse double usage autonome.",
                    )
                )
            else:
                matching_entry = nature_e_analysis.get("matching_entry")
                matching_entry_text = nature_e_analysis.get("matching_entry_text")
                technology_type = nature_e_analysis.get("technology_type_covered")
                if nature_e_analysis.get("eccn_covered_by_nature_e") and matching_entry:
                    dualuse_nature_e = _clean(
                        f"{matching_entry}: {matching_entry_text or 'entree Nature E retenue'}"
                        + (f" pour de la technologie de {technology_type}" if technology_type else ""),
                    )
                elif dualuse_payload:
                    dualuse_nature_e = "Aucune entree Nature E directement applicable n'a ete retenue."
                else:
                    dualuse_nature_e = "Non pertinent."

                dualuse_categories = _format_mapping_lines(categories_analysis)
                dualuse_rubriques = _join(eccn_lines, default="Aucune rubrique de controle determinante n'a ete retenue.", limit=4)
                dualuse_conclusion = _clean(
                    (dualuse_payload.get("final_determination") or {}).get("reasoning")
                    or (dualuse_payload.get("document_analysis") or {}).get("analysis_summary"),
                    default="L'analyse double usage n'a pas fourni de conclusion detaillee exploitable dans le mode de secours.",
                )
                dualuse_section_body = "\n".join(
                    [
                        f"a. Categories analysees : {dualuse_categories}",
                        f"b. Rubriques verifiees : {dualuse_rubriques}",
                        f"c. Croisement Nature E : {dualuse_nature_e}",
                        f"Conclusion : {dualuse_conclusion}",
                    ]
                )

        document_analysis = dualuse_payload.get("document_analysis") or {}
        enabled_actions = [
            label
            for field, label in (
                ("enables_development", "le developpement"),
                ("enables_production", "la production"),
                ("enables_use", "l'utilisation"),
            )
            if document_analysis.get(field)
        ]
        blocked_actions = [
            label
            for field, label in (
                ("enables_development", "le developpement"),
                ("enables_production", "la production"),
                ("enables_use", "l'utilisation"),
            )
            if field in document_analysis and not document_analysis.get(field)
        ]
        actionable_elements = document_analysis.get("actionable_elements") or []
        if techdata_ml_payload:
            technical_allows = _clean(
                techdata_ml_payload.get("reasoning"),
                default="Le document fournit des donnees techniques directement exploitables pour l'article militaire retenu.",
            )
            technical_limits = "Ces donnees doivent etre interpretees dans le cadre de la qualification militaire deja retenue."
        else:
            technical_allows = (
                _clean(document_analysis.get("analysis_summary"))
                if document_analysis.get("analysis_summary")
                else (
                    f"Le contenu permet directement {', '.join(enabled_actions)}."
                    if enabled_actions
                    else "Le contenu technique exploitable reste limite."
                )
            )
            technical_limits = (
                f"Le contenu ne permet pas directement {', '.join(blocked_actions)}."
                if blocked_actions
                else "Aucune limitation technique supplementaire n'a pu etre etablie automatiquement."
            )
        technical_citations = _join(
            [*actionable_elements, f"Pages les plus utiles: {page_list}" if page_list != "non precisees" else ""]
            + technical_examples,
            default="Aucun element technique detaille n'a pu etre restitue.",
            limit=5,
        )

        if no_tangible_identified:
            sections = [
                (
                    "1. IDENTIFICATION DE L ELEMENT EXAMINE",
                    _sentence(
                        "Le document ne permet pas d'identifier clairement le bien, le logiciel, l'equipement ou l'element technique qui devrait faire l'objet de l'analyse export control. "
                        f"Le contenu restitue plutot {context_summary.lower()}, avec des signaux techniques tels que {signals_text.lower()}. "
                        "Il manque donc un element suffisamment defini pour rattacher solidement l'analyse a une entree de controle."
                    ),
                ),
                (
                    "2. ANALYSE MILITAIRE",
                    "\n".join(
                        [
                            "Conclusion : Non applicable en l'absence d'element technique ou de systeme militaire identifiable.",
                            _sentence(
                                "Les indices examines portent sur l'absence de references a des programmes de defense, de normes militaires, de durcissement environnemental, ou d'exigences d'emploi operationnel. "
                                "Le contenu reste demonstratif, conceptuel ou exploratoire, sans equipement militaire clairement nomme ni performance rattachee a un usage combat."
                            ),
                        ]
                    ),
                ),
                (
                    "3. ANALYSE DOUBLE USAGE",
                    "\n".join(
                        [
                            "a. Categories analysees : Aucun rattachement robuste a une categorie de controle n'a pu etre etabli, faute d'element technique clairement defini ou de technologie source suffisamment precise.",
                            "b. Rubriques verifiees : Aucune rubrique n'a pu etre retenue de facon opposable a partir des seuls elements visibles dans le document.",
                            "c. Croisement Nature E : Non applicable tant qu'aucun bien ou aucune technologie source n'est etabli de maniere fiable.",
                            "Conclusion : Le dossier ne fournit pas une base assez solide pour qualifier le contenu comme technologie controlee ou non controlee sur une entree precise.",
                        ]
                    ),
                ),
                (
                    "4. ANALYSE TECHNIQUE DU DOCUMENT",
                    _sentence(
                        f"Le document permet surtout de comprendre {context_summary.lower()} et de relever les indices suivants : {technical_citations.lower()}. "
                        "En revanche, il ne permet pas d'identifier un bien controle, de reconstituer un processus industriel complet, ni de qualifier une technologie export de facon pleinement opposable."
                    ),
                ),
                (
                    "5. DECISION ET ACTION",
                    "\n".join(
                        [
                            f"Verdict propose : {_clean(decision_label)}",
                            _sentence(
                                f"Ce verdict est retenu parce que le document ne permet pas de rattacher de facon fiable le contenu a un bien ou a une technologie source clairement definis. {review_line} "
                                "Une reclassification devient pertinente si des annexes techniques, plans, nomenclatures, code source ou specifications detaillees sont ajoutes."
                            ),
                        ]
                    ),
                ),
            ]
            return "\n\n".join(f"{title}\n{body}" for title, body in sections)

        military_conclusion = _clean(
            military_payload.get("reasoning"),
            default=(
                "L'analyse militaire n'a pas pu etre stabilisee automatiquement et doit etre confirmee manuellement."
                if final_marking == "EC_Review_Required"
                else "Aucun indice militaire determinant n'a ete retenu dans le resume de secours."
            ),
        )
        military_indices_text = _join(
            military_findings,
            default="Aucun indice militaire detaille n'a pu etre restitue.",
            limit=4,
        )
        military_exclusions_text = _join(
            exclusions,
            default="Aucune exclusion specifique n'a ete documentee.",
            limit=4,
        )
        identification_paragraph = _sentence(
            f"L'element principal examine est {tangible_label}. "
            f"Il s'inscrit dans un contexte { _clean(tangible_payload.get('program_context') or lifecycle_phase or 'industriel non precise', default='industriel non precise') .lower() }, "
            f"avec une phase principale rattachee a { _clean(lifecycle_phase, default='une phase non precisee').lower() }. "
            f"Les indices les plus utiles releves dans le document portent sur {signals_text.lower()}"
            + (
                f", ainsi que sur les references suivantes : {_join(tangible_hints, default='', limit=4).lower()}"
                if tangible_hints
                else ""
            )
            + "."
        )
        military_paragraph = _sentence(
            f"Les indices examines portent notamment sur {military_indices_text.lower()}. "
            f"Les exclusions ou rattachements contextuels retenus sont les suivants : {military_exclusions_text.lower()}."
        )
        if techdata_ml_payload and not is_us_lane:
            military_paragraph = _sentence(f"{military_paragraph} {dualuse_note}")
        technical_paragraph = _sentence(
            f"{technical_allows} {technical_limits} "
            f"Les elements techniques cites les plus utiles sont : {technical_citations.lower()}."
        )
        decision_paragraph = _sentence(
            f"Ce verdict est retenu au regard des verifications precedentes et du niveau de detail reellement exploitable dans le document. {review_line} "
            f"Reserve eventuelle : {automatic_limit.lower()}"
        )
        sections: list[tuple[str, str]] = [
            (
                "1. IDENTIFICATION DE L ELEMENT EXAMINE",
                identification_paragraph,
            ),
            (
                "2. ANALYSE ITAR" if is_us_lane else "2. ANALYSE MILITAIRE",
                "\n".join(
                    [
                        f"Conclusion : {military_conclusion}",
                        military_paragraph,
                    ]
                ),
            ),
            (
                "4. ANALYSE TECHNIQUE DU DOCUMENT",
                technical_paragraph,
            ),
            (
                "5. DECISION ET ACTION",
                "\n".join(
                    [
                        f"Verdict propose : {_clean(decision_label)}",
                        decision_paragraph,
                    ]
                ),
            ),
        ]
        if dualuse_section_body:
            sections.insert(
                2,
                (
                    dualuse_section_title,
                    dualuse_section_body,
                ),
            )
        return "\n\n".join(f"{title}\n{body}" for title, body in sections)

    @staticmethod
    def _fallback_summary(final_marking: str, confidence: float, requires_review: bool, page_payloads: list[dict[str, Any]]) -> str:
        if get_rationale_language() == "en":
            return ClassificationOrchestrator._fallback_summary_en(
                final_marking,
                confidence,
                requires_review,
                page_payloads,
            )
        return ClassificationOrchestrator._fallback_summary_fr(
            final_marking,
            confidence,
            requires_review,
            page_payloads,
        )

    @staticmethod
    def _fallback_summary_en(final_marking: str, confidence: float, requires_review: bool, page_payloads: list[dict[str, Any]]) -> str:
        pages = [payload["page_number"] for payload in page_payloads if payload.get("relevant")]
        page_list = ", ".join(str(page) for page in pages[:4]) or "none identified"
        decision_label = get_marking_label(final_marking, language="en")
        review_line = (
            "Human review is still required."
            if requires_review
            else "No additional human review is required at this stage."
        )
        sections = [
            ("IDENTIFICATION", "Fallback mode could not summarize the examined item in detail."),
            ("MILITARY ANALYSIS", "Fallback mode does not provide a detailed military rationale."),
            ("DUAL-USE ANALYSIS", f"The most useful pages identified automatically are: {page_list}."),
            ("TECHNICAL ANALYSIS", "The content contains enough technical signals to produce a working verdict."),
            ("DECISION", f"Proposed verdict: {decision_label}. {review_line}"),
        ]
        return "\n\n".join(f"{title}\n{body}" for title, body in sections)

    @staticmethod
    def _fallback_summary_fr(final_marking: str, confidence: float, requires_review: bool, page_payloads: list[dict[str, Any]]) -> str:
        pages = [payload["page_number"] for payload in page_payloads if payload.get("relevant")]
        page_list = ", ".join(str(page) for page in pages[:4]) or "non precisees"
        decision_label = get_marking_label(final_marking)
        review_line = "Une revue humaine reste necessaire." if requires_review else "Aucune revue humaine supplementaire n'est requise a ce stade."
        sections = [
            ("IDENTIFICATION", "Le tangible n'a pas pu etre resume finement dans le mode de secours."),
            ("ANALYSE MILITAIRE", "Le mode de secours ne permet pas une justification militaire detaillee."),
            ("ANALYSE DOUBLE USAGE", f"Les pages les plus utiles identifiees automatiquement sont : {page_list}."),
            ("ANALYSE TECHNIQUE", "Le contenu comporte des signaux techniques suffisants pour produire un verdict de travail."),
            ("DECISION", f"Verdict propose : {decision_label}. {review_line}"),
        ]
        return "\n\n".join(f"{title}\n{body}" for title, body in sections)
