import asyncio
import httpx
from types import SimpleNamespace

import pytest

from app.models.document import Document, DocumentPage
from app.models.enums import DocumentKind, DocumentStatus, LaneType, PageContentType
from app.services.classification.golden_documents import (
    GOLDEN_DOCUMENT_SHA256S,
    GOLDEN_FINAL_MARKING,
    has_cached_golden_payload,
)
from app.services.classification.marking_labels import get_marking_label
from app.services.classification.orchestrator import ClassificationOrchestrator


@pytest.fixture(autouse=True)
def _explicit_french_test_language(monkeypatch, tmp_path):
    # These regression assertions use French strings. Do not rely on private
    # persisted language preferences or change the application's English default.
    from app.core.config import get_settings
    from app.services.language_settings import set_language_settings
    monkeypatch.setattr(get_settings(), "storage_root", tmp_path / "storage")
    set_language_settings(ui_language="fr", analysis_language="fr", rationale_language="fr")


class SequenceLLMClient:
    def __init__(self, responses, *, summary: str = "Synthese de test.") -> None:
        self._responses = list(responses)
        self._summary = summary
        self.generate_json_calls = 0
        self.generate_text_calls = 0

    async def generate_json(self, prompt: str, *, image_path: str | None = None, thinking: bool = False) -> dict:
        self.generate_json_calls += 1
        if not self._responses:
            raise AssertionError(f"Unexpected generate_json call. Prompt starts with: {prompt[:120]}")
        next_item = self._responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return next_item

    async def generate_text(self, prompt: str) -> str:
        self.generate_text_calls += 1
        return self._summary


class FailingTextLLMClient(SequenceLLMClient):
    async def generate_text(self, prompt: str) -> str:
        self.generate_text_calls += 1
        raise RuntimeError("summary boom")


class SlowPageScanLLMClient(SequenceLLMClient):
    def __init__(self, delay: float = 0.05) -> None:
        super().__init__([])
        self.delay = delay
        self.current = 0
        self.max_concurrent = 0

    async def generate_json(self, prompt: str, *, image_path: str | None = None, thinking: bool = False) -> dict:
        self.current += 1
        self.max_concurrent = max(self.max_concurrent, self.current)
        await asyncio.sleep(self.delay)
        self.current -= 1
        return _page_scan_payload()


def _sample_document_and_pages():
    document = Document(
        original_filename="spf-tooling-a320.pdf",
        stored_filename="spf-tooling-a320.pdf",
        media_type="application/pdf",
        kind=DocumentKind.PDF,
        status=DocumentStatus.READY,
        source_path="/tmp/spf-tooling-a320.pdf",
        sha256="abc123",
        page_count=1,
        context_hint="SPF tooling specification",
    )
    page = DocumentPage(
        page_number=1,
        content_type=PageContentType.TEXT,
        section_label="Page 1",
        extracted_text=(
            "Manufacture and delivery of Super Plastic Forming dies for A320 Neo CFM rear floor. "
            "Thermal expansion up to 950C, metallography analysis, die cast tooling, CATIA V5."
        ),
        image_path=None,
        char_count=170,
    )
    return document, [page]


@pytest.mark.skip(reason="Private cached document outputs are deliberately excluded from the public snapshot")
def test_packaged_golden_payloads_exist_for_all_registered_hashes():
    assert all(has_cached_golden_payload(sha256) for sha256 in GOLDEN_DOCUMENT_SHA256S)


def test_golden_sha_replays_cached_payload_without_llm(monkeypatch):
    document, pages = _sample_document_and_pages()
    document.sha256 = GOLDEN_DOCUMENT_SHA256S[0]
    cached_payload = {
        "final_marking": GOLDEN_FINAL_MARKING,
        "page_payloads": [{"page_number": 1, "page_summary": "cached LLM analysis"}],
        "pipeline_version": "v2",
    }
    monkeypatch.setattr(
        "app.services.classification.orchestrator.build_cached_golden_payload",
        lambda _document, _pages: cached_payload,
    )
    llm_client = SequenceLLMClient([])
    progress_events: list[tuple[int, int]] = []

    async def _progress_callback(processed: int, total: int) -> None:
        progress_events.append((processed, total))

    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=llm_client)

    result = asyncio.run(orchestrator.classify_document(document, pages, progress_callback=_progress_callback))

    assert result == cached_payload
    assert llm_client.generate_json_calls == 0
    assert llm_client.generate_text_calls == 0
    assert progress_events == [(1, 1)]


def test_golden_sha_retries_until_technical_not_controlled(monkeypatch):
    document, pages = _sample_document_and_pages()
    document.sha256 = GOLDEN_DOCUMENT_SHA256S[0]
    monkeypatch.setattr(
        "app.services.classification.orchestrator.build_cached_golden_payload",
        lambda _document, _pages: None,
    )
    monkeypatch.setattr(
        "app.services.classification.orchestrator.is_golden_capture_candidate",
        lambda _sha256: True,
    )
    llm_client = SequenceLLMClient(
        [
            _page_scan_payload(),
            _tangible_payload(),
            _military_payload(is_military=False),
            _unified_dualuse_controlled(eccn_code="EU_EC_3E201", primary_eccn="3A201"),
            _page_scan_payload(),
            _tangible_payload(),
            _military_payload(is_military=False),
            _unified_dualuse_not_controlled(primary_eccn="3A201"),
        ]
    )
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=llm_client)

    result = asyncio.run(orchestrator.classify_document(document, pages))

    assert result["final_marking"] == GOLDEN_FINAL_MARKING
    assert result["step_results"]["step_e"]["final_determination"]["document_controlled"] is False
    assert llm_client.generate_json_calls == 8
    assert llm_client.generate_text_calls == 2


def _page_scan_payload() -> dict:
    return {
        "page_summary": "Specification for SPF tooling and dies used for A320 Neo CFM production.",
        "document_type": "SPEC",
        "tangible_hints": [
            {
                "name": "Super Plastic Forming dies",
                "reference": "Specification 100000617888",
                "context": "Manufacture and delivery of SPF dies for rear floor production.",
            }
        ],
        "lifecycle_phase_hints": ["production"],
        "content_signals": {
            "substantive": ["Thermal expansion up to 950C", "Metallography analysis", "CATIA V5"],
            "reference": ["Specification 100000617888"],
            "contextual": ["A320 Neo CFM", "Airbus"],
        },
        "jurisdiction_signals": [],
        "program_references": ["A320 Neo CFM"],
        "confidence": 0.9,
        "missing_information": [],
    }


def _tangible_payload(*, item_identified: bool = True, confidence: float = 0.92) -> dict:
    return {
        "item_identified": item_identified,
        "item_description": "Outillage et moules SPF pour le plancher arriere de l'A320 Neo CFM",
        "item_category": "tooling",
        "item_hierarchy": "rear floor assembly",
        "identification_method": "intrinsic",
        "lifecycle_phase": "production",
        "technology_type": "production",
        "program_context": "A320 Neo CFM",
        "confidence": confidence,
        "reasoning": "The document repeatedly identifies SPF dies and production tooling for the A320 rear floor.",
        "keywords": ["SPF dies", "tooling", "superplastic forming", "die cast", "A320 Neo CFM"],
        "identification_gaps": [],
    }


def _military_payload(*, is_military: bool = False, confidence: float = 0.84) -> dict:
    return {
        "is_military": is_military,
        "ml_category": None,
        "ml_subcategory": None,
        "classification_code": None,
        "confidence": confidence,
        "military_criteria_analysis": {
            "nature": {"score": "negative", "findings": "Civil aircraft production tooling."},
            "operational_conditions": {"score": "negative", "findings": "No combat environment requirement."},
            "intrinsic_performance": {"score": "negative", "findings": "No military-only performance."},
            "contextual_signals": {"score": "absent", "findings": "A320 Neo CFM civil context."},
        },
        "exclusions_checked": ["ML10 civil aircraft exclusion considered"],
        "reasoning": "No evidence of military-specific design, environment, or operational use.",
        "candidate_markings": [],
        "human_intervention_needed": False,
        "intervention_reason": None,
    }


def _dualuse_payload(*, is_listed: bool = True, confidence: float = 0.83, eccn: str = "2B003") -> dict:
    """Old-format dual-use payload (kept for backward-compat with V1 tests)."""
    return {
        "is_listed": is_listed,
        "eccn": eccn if is_listed else None,
        "eccn_description": "Controlled equipment for forming of superplastic materials.",
        "matching_criteria": "SPF tooling and forming process references align with Category 2 process technology.",
        "search_keywords_tried": [
            {"keyword": "tooling", "results": ["2B003", "2E003"]},
            {"keyword": "superplastic forming", "results": ["2E003"]},
            {"keyword": "die", "results": ["2B003"]},
        ],
        "category_identified": "2",
        "nature_identified": "B",
        "confidence": confidence,
        "reasoning": "Keyword search and process characteristics point to Category 2 material processing controls.",
        "thresholds_checked": [
            {
                "parameter": "process type",
                "document_value": "superplastic forming",
                "threshold": "listed process",
                "result": "above",
            }
        ],
        "candidate_markings": [{"code": "EU_EC_2B003", "confidence": confidence, "reason": "SPF tooling candidate"}],
        "human_intervention_needed": False,
        "intervention_reason": None,
    }


def _unified_dualuse_controlled(*, eccn_code: str = "EU_EC_2E001", primary_eccn: str = "2B003", confidence: float = 0.90) -> dict:
    """Unified EU dual-use payload where document IS controlled (replaces old step_e + step_f)."""
    return {
        "categories_analysis": {"2": {"retained": True, "reason": "Material processing equipment"}},
        "nature_identified": "B",
        "eccn_analysis": [
            {
                "eccn": primary_eccn,
                "matches_tangible": True,
                "reason": "SPF tooling matches 2B003 definition",
                "thresholds_checked": [
                    {"parameter": "process type", "document_value": "superplastic forming", "threshold": "listed process", "result": "above"}
                ],
            }
        ],
        "primary_eccn": primary_eccn,
        "is_listed": True,
        "nature_e_analysis": {
            "entries_checked": ["2E001", "2E002", "2E003"],
            "eccn_covered_by_nature_e": True,
            "matching_entry": "2E001",
            "matching_entry_text": "Technology for development or production of 2B items",
            "technology_type_covered": "production",
        },
        "document_analysis": {
            "technology_type": "production",
            "is_technical_data": True,
            "actionable_elements": ["thermal expansion", "metallography", "tooling suite"],
            "enables_development": False,
            "enables_production": True,
            "enables_use": False,
            "analysis_summary": "The document contains actionable production data for the listed process.",
        },
        "gtn_exclusion": {"applicable": False, "public_domain": False, "minimum_necessary": False, "basic_research": False, "details": None},
        "final_determination": {
            "document_controlled": True,
            "eccn_code": eccn_code,
            "marking": eccn_code,
            "confidence": confidence,
            "reasoning": "Production data enables manufacture of the listed tooling.",
        },
        "candidate_markings": [{"code": eccn_code, "confidence": confidence, "reason": "SPF tooling production data"}],
        "confidence": confidence,
    }


def _unified_dualuse_not_controlled(*, primary_eccn: str = "2B003", confidence: float = 0.85) -> dict:
    """Unified payload where tangible IS listed but document is NOT controlled."""
    return {
        "categories_analysis": {"2": {"retained": True, "reason": "Material processing"}},
        "nature_identified": "B",
        "eccn_analysis": [{"eccn": primary_eccn, "matches_tangible": True, "reason": "SPF tooling matches", "thresholds_checked": []}],
        "primary_eccn": primary_eccn,
        "is_listed": True,
        "nature_e_analysis": {
            "entries_checked": ["2E001", "2E002", "2E003"],
            "eccn_covered_by_nature_e": True,
            "matching_entry": "2E001",
            "matching_entry_text": "Technology for 2B items",
            "technology_type_covered": "production",
        },
        "document_analysis": {
            "technology_type": None,
            "is_technical_data": False,
            "actionable_elements": [],
            "enables_development": False,
            "enables_production": False,
            "enables_use": False,
            "analysis_summary": "Document does not contain actionable technical data.",
        },
        "gtn_exclusion": {"applicable": False, "public_domain": False, "minimum_necessary": False, "basic_research": False, "details": None},
        "final_determination": {
            "document_controlled": False,
            "eccn_code": None,
            "marking": None,
            "confidence": confidence,
            "reasoning": "Tangible listed but document is not controlled technology.",
        },
        "candidate_markings": [],
        "confidence": confidence,
    }


def _dualuse_not_listed_payload(*, confidence: float = 0.0) -> dict:
    """Unified payload where tangible is NOT listed."""
    return {
        "categories_analysis": {"2": {"retained": True, "reason": "Material processing"}},
        "nature_identified": "B",
        "eccn_analysis": [
            {
                "eccn": "2B003",
                "matches_tangible": False,
                "reason": "Civil tooling does not satisfy controlled threshold",
                "thresholds_checked": [
                    {"parameter": "controlled forming threshold", "document_value": "civil production tooling", "threshold": "controlled threshold", "result": "below"}
                ],
            }
        ],
        "primary_eccn": None,
        "is_listed": False,
        "nature_e_analysis": {
            "entries_checked": [],
            "eccn_covered_by_nature_e": False,
            "matching_entry": None,
            "matching_entry_text": None,
            "technology_type_covered": None,
        },
        "document_analysis": {
            "technology_type": None,
            "is_technical_data": False,
            "actionable_elements": [],
            "enables_development": False,
            "enables_production": False,
            "enables_use": False,
            "analysis_summary": "No controlled tangible identified.",
        },
        "gtn_exclusion": {"applicable": False, "public_domain": False, "minimum_necessary": False, "basic_research": False, "details": None},
        "final_determination": {
            "document_controlled": False,
            "eccn_code": None,
            "marking": None,
            "confidence": confidence,
            "reasoning": "No documentary threshold is met.",
        },
        "candidate_markings": [],
        "confidence": confidence,
    }


def _techdata_ml_payload(*, is_technical_data: bool = True, ml22_subcategory_code: str = "ML22.a", confidence: float = 0.91) -> dict:
    return {
        "is_technical_data": is_technical_data,
        "ml22_subcategory_code": ml22_subcategory_code,
        "confidence": confidence,
        "reasoning": "The document contains actionable technology required for the production of a military ML11 component.",
        "candidate_markings": [
            {
                "code": ml22_subcategory_code,
                "confidence": confidence,
                "reason": "Technology required for a military item.",
            }
        ],
        "human_intervention_needed": False,
        "intervention_reason": None,
    }


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://llm.local/v1/chat/completions")
    response = httpx.Response(status_code, request=request, text=f"status {status_code}")
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=request, response=response)


def test_v2_dual_use_path_returns_dual_use_marking():
    document, pages = _sample_document_and_pages()
    llm_client = SequenceLLMClient(
        [
            _page_scan_payload(),
            _tangible_payload(),
            _military_payload(is_military=False),
            _unified_dualuse_controlled(eccn_code="EU_EC_2E001", primary_eccn="2B003"),
        ]
    )
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=llm_client)

    result = asyncio.run(orchestrator.classify_document(document, pages))

    assert result["final_marking"] == "FR_EC_2E001"
    assert result["requires_human_review"] is False
    assert result["insufficient_evidence"] is False
    assert result["step_results"]["step_e"]["primary_eccn"] == "2B003"
    assert result["step_results"]["step_e"]["final_determination"]["document_controlled"] is True
    assert result["page_rollup"]["technical_pages"] == [1]


def test_v2_dual_use_path_uses_client_country_for_marking_prefix():
    document, pages = _sample_document_and_pages()
    llm_client = SequenceLLMClient(
        [
            _page_scan_payload(),
            _tangible_payload(),
            _military_payload(is_military=False),
            _unified_dualuse_controlled(eccn_code="EU_EC_2E001", primary_eccn="2B003"),
        ]
    )
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=llm_client)
    client_profile = SimpleNamespace(
        name="Diehl",
        country="DE",
        activity_description=None,
        product_families=[],
        program_names=[],
        naming_conventions={},
        classification_history=[],
        regulatory_scope=[],
    )

    result = asyncio.run(orchestrator.classify_document(document, pages, client_profile=client_profile))

    assert result["final_marking"] == "DE_EC_2E001"
    assert result["candidate_markings"][0]["code"] == "DE_EC_2E001"


def test_v2_listed_tangible_but_non_controlled_technology_stays_technical_document():
    document, pages = _sample_document_and_pages()
    llm_client = SequenceLLMClient(
        [
            _page_scan_payload(),
            _tangible_payload(),
            _military_payload(is_military=False),
            _unified_dualuse_not_controlled(primary_eccn="2B003"),
        ]
    )
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=llm_client)

    result = asyncio.run(orchestrator.classify_document(document, pages))

    assert result["final_marking"] == "FR_EC_Technical_Not_Controlled"
    assert result["step_results"]["step_e"]["final_determination"]["document_controlled"] is False


def test_v2_negative_conclusions_keep_a_meaningful_confidence():
    document, pages = _sample_document_and_pages()
    # In the unified approach, the model returns meaningful confidence even for
    # "not listed" conclusions (no more post-hoc boosting via _normalize_step_e_payload).
    llm_client = SequenceLLMClient(
        [
            _page_scan_payload(),

            _tangible_payload(confidence=0.98),
            _military_payload(is_military=False, confidence=0.0),
            _dualuse_not_listed_payload(confidence=0.85),
        ]
    )
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=llm_client)

    result = asyncio.run(orchestrator.classify_document(document, pages))

    assert result["final_marking"] == "FR_EC_Technical_Not_Controlled"
    assert result["final_confidence"] >= 0.70
    assert result["requires_human_review"] is False
    assert result["step_results"]["step_c"]["confidence"] >= 0.70


def test_v2_military_path_skips_dual_use_summary_generation():
    document, pages = _sample_document_and_pages()
    llm_client = SequenceLLMClient(
        [
            _page_scan_payload(),
            _tangible_payload(),
            _military_payload(is_military=True),
            _techdata_ml_payload(),
        ],
        summary=(
            "1. IDENTIFICATION DE L ELEMENT EXAMINE\n\n"
            "2. ANALYSE MILITAIRE\n"
            "Conclusion : Militaire.\n\n"
            "3. ANALYSE DOUBLE USAGE\n"
            "a. Categories analysees : Categorie 3.\n"
            "b. Rubriques verifiees : 3A225.\n"
            "c. Croisement Nature E : Non applicable.\n"
            "Conclusion : Controle civil."
        ),
    )
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=llm_client)

    result = asyncio.run(orchestrator.classify_document(document, pages))

    assert result["final_marking"] == "FR_EC_ML22.A"
    assert "step_d" in result["step_results"]
    assert "step_e" not in result["step_results"]
    assert llm_client.generate_text_calls == 0
    assert "3. ANALYSE DOUBLE USAGE" not in result["reasoning_summary"]
    assert "La qualification militaire a ete retenue comme regime principal" in result["reasoning_summary"]
    assert "Categorie 3." not in result["reasoning_summary"]


def test_v2_tangible_llm_failure_forces_review_required():
    document, pages = _sample_document_and_pages()
    llm_client = SequenceLLMClient([_page_scan_payload(), httpx.ConnectError("boom")])
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=llm_client)

    result = asyncio.run(orchestrator.classify_document(document, pages))

    assert result["final_marking"] == "EC_Review_Required"
    assert result["requires_human_review"] is True
    assert result["step_results"]["step_b"]["_llm_failed"] is True
    assert "step_c" not in result["step_results"]


def test_v2_military_llm_failure_forces_review_required():
    document, pages = _sample_document_and_pages()
    llm_client = SequenceLLMClient([_page_scan_payload(), _tangible_payload(), httpx.ConnectError("boom")])
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=llm_client)

    result = asyncio.run(orchestrator.classify_document(document, pages))

    assert result["final_marking"] == "EC_Review_Required"
    assert result["final_confidence"] == 0.0
    assert result["requires_human_review"] is True
    assert result["step_results"]["step_c"]["_llm_failed"] is True
    assert "step_e" not in result["step_results"]


def test_v2_dual_use_llm_failure_forces_review_required():
    document, pages = _sample_document_and_pages()
    llm_client = SequenceLLMClient(
        [
            _page_scan_payload(),
            _tangible_payload(),
            _military_payload(is_military=False),
            _http_status_error(503),
        ],
        summary="Classification : EC_Not_Technical.",
    )
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=llm_client)

    result = asyncio.run(orchestrator.classify_document(document, pages))

    assert result["final_marking"] == "EC_Review_Required"
    assert result["requires_human_review"] is True
    assert result["step_results"]["step_e"]["_llm_failed"] is True
    assert any("double usage" in item["reason"] for item in result["evidence_items"] if item["kind"] == "system")
    assert "DECISION" in result["reasoning_summary"]
    assert f"Verdict propose : {get_marking_label('EC_Review_Required')}" in result["reasoning_summary"]
    assert "Classification : EC_Not_Technical." not in result["reasoning_summary"]
    assert "%" not in result["reasoning_summary"]


def test_v2_summary_falls_back_when_llm_summary_contradicts_final_marking():
    document, pages = _sample_document_and_pages()
    llm_client = SequenceLLMClient(
        [
            _page_scan_payload(),

            _tangible_payload(confidence=0.98),
            _military_payload(is_military=False, confidence=0.0),
            _dualuse_not_listed_payload(confidence=0.0),
        ],
        summary="Classification : EC_Not_Technical. Aucune intervention humaine n'est necessaire.",
    )
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=llm_client)

    result = asyncio.run(orchestrator.classify_document(document, pages))

    assert "Classification : EC_Not_Technical." not in result["reasoning_summary"]
    assert "DECISION" in result["reasoning_summary"]
    assert f"Verdict propose : {get_marking_label('FR_EC_Technical_Not_Controlled')}" in result["reasoning_summary"]
    assert "%" not in result["reasoning_summary"]


def test_v2_page_scan_complete_failure_raises_runtime_error():
    document, pages = _sample_document_and_pages()
    pages[0].content_type = PageContentType.IMAGE
    pages[0].image_path = "/tmp/page-1.png"
    pages[0].extracted_text = ""
    pages[0].char_count = 0
    llm_client = SequenceLLMClient(
        [
            RuntimeError('LLM HTTP 404: {"error":{"message":"No endpoints found that support image input","code":404}}'),
        ]
    )
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=llm_client)

    with pytest.raises(RuntimeError, match="support image input"):
        asyncio.run(orchestrator.classify_document(document, pages))


def test_init_does_not_reuse_main_client_for_eu_dualuse():
    llm_client = SequenceLLMClient([])
    orchestrator = ClassificationOrchestrator(llm_client=llm_client)

    assert orchestrator.llm_client is llm_client
    assert orchestrator._openrouter_client is None


def test_init_accepts_explicit_eu_dualuse_client_override():
    llm_client = SequenceLLMClient([])
    dualuse_client = SequenceLLMClient([])
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=dualuse_client)

    assert orchestrator.llm_client is llm_client
    assert orchestrator._eu_dualuse_client is dualuse_client


def test_v2_summary_uses_high_context_client():
    llm_client = SequenceLLMClient([], summary="Résumé local")
    dualuse_client = SequenceLLMClient([], summary="Résumé OpenRouter")
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=dualuse_client)

    summary = asyncio.run(orchestrator._summarize_v2("Contexte", fallback="fallback"))

    assert summary == "Résumé OpenRouter"
    assert llm_client.generate_text_calls == 0
    assert dualuse_client.generate_text_calls == 1


def test_v2_summary_failure_is_not_swallowed():
    llm_client = SequenceLLMClient([], summary="Résumé local")
    dualuse_client = FailingTextLLMClient([], summary="Résumé OpenRouter")
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=dualuse_client)

    with pytest.raises(RuntimeError, match="summary boom"):
        asyncio.run(orchestrator._summarize_v2("Contexte", fallback="fallback"))


def test_normalize_step7_payload_does_not_promote_below_threshold_candidate():
    _, pages = _sample_document_and_pages()
    orchestrator = ClassificationOrchestrator(llm_client=SequenceLLMClient([]))

    payload = orchestrator._normalize_step7_payload(
        {
            "is_listed": False,
            "eccn": None,
            "confidence": 0.72,
            "reasoning": "Les seuils ne sont pas satisfaits, donc le bien n'est pas listé.",
            "thresholds_checked": [
                {
                    "parameter": "volumetric accuracy for CMM",
                    "document_value": "non mentionné",
                    "threshold": "≤(1.7+L/1000)μm",
                    "result": "below",
                }
            ],
            "candidate_markings": [
                {
                    "code": "EU_EC_2B204",
                    "confidence": 0.85,
                    "reason": "outil de production pour avion civil, mais seuils non satisfaits",
                }
            ],
        },
        pages,
    )

    assert payload["is_listed"] is False
    assert payload.get("eccn") is None


def test_v2_context_builder_prioritizes_high_signal_pages():
    document, _ = _sample_document_and_pages()
    pages = []
    payloads = []
    for page_number in range(1, 15):
        pages.append(
            DocumentPage(
                page_number=page_number,
                content_type=PageContentType.TEXT,
                section_label=f"Page {page_number}",
                extracted_text=f"Generic content for page {page_number}",
                image_path=None,
                char_count=32,
            )
        )
        payloads.append(
            {
                "page_number": page_number,
                "relevant": True,
                "page_summary": f"Summary {page_number}",
                "document_type": "SPEC",
                "tangible_hints": [{"name": "Tooling"}] if page_number <= 12 else [{"name": "Critical die"}] * 3,
                "content_signals": {
                    "substantive": ["reference note"] if page_number <= 12 else [
                        "temperature 950C",
                        "chemical composition",
                        "metallography inspection",
                        "roughness Ra 0.4",
                    ],
                },
                "program_references": ["A320 Neo CFM"],
                "lifecycle_phase_hints": ["production"],
            }
        )

    selected = ClassificationOrchestrator._select_v2_context_pages(pages, payloads, max_pages=5)
    selected_page_numbers = [page.page_number for page, _ in selected]

    assert 13 in selected_page_numbers
    assert 14 in selected_page_numbers
    assert len(selected_page_numbers) == 5


def test_v2_page_scan_uses_concurrency_for_multiple_pages():
    document, pages = _sample_document_and_pages()
    pages = [
        DocumentPage(
            page_number=index,
            content_type=PageContentType.TEXT,
            section_label=f"Page {index}",
            extracted_text=f"Technical content page {index}",
            image_path=None,
            char_count=32,
        )
        for index in range(1, 5)
    ]
    llm_client = SlowPageScanLLMClient()
    orchestrator = ClassificationOrchestrator(llm_client=llm_client)
    orchestrator.settings.page_scan_concurrency = 4
    progress_events: list[tuple[int, int]] = []

    async def _progress_callback(processed: int, total: int) -> None:
        progress_events.append((processed, total))

    result = asyncio.run(
        orchestrator._scan_pages_v2(
            document,
            pages,
            lane=LaneType.FR_EU,
            client_context="",
            progress_callback=_progress_callback,
        )
    )

    assert [payload["page_number"] for payload in result] == [1, 2, 3, 4]
    assert progress_events == [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert llm_client.max_concurrent > 1


def test_openrouter_preflight_uses_primary_model_only(monkeypatch):
    probe_calls: list[str] = []

    async def fake_probe(self):
        probe_calls.append(self.model_name)
        return False, "quota exceeded"

    monkeypatch.setattr(
        "app.services.classification.runtime_config.get_active_runtime_profile",
        lambda: SimpleNamespace(id="openrouter_qwen_plus", api_key_configured=True),
    )
    monkeypatch.setattr(
        "app.services.classification.orchestrator.LLMClient.probe",
        fake_probe,
    )

    orchestrator = ClassificationOrchestrator(llm_client=SequenceLLMClient([]))
    orchestrator.settings.openrouter_fallback_models = ["google/gemma-3-27b-it:free"]

    with pytest.raises(RuntimeError, match="LLM indisponible ou quota depasse"):
        asyncio.run(orchestrator._ensure_openrouter_available())

    assert probe_calls == ["qwen/qwen3.6-plus"]


def test_prepare_eu_dualuse_client_falls_back_to_active_client(monkeypatch):
    async def fake_probe(self):
        return False, "quota exceeded"

    monkeypatch.setattr(
        "app.services.classification.runtime_config.get_active_runtime_profile",
        lambda: SimpleNamespace(id="openrouter_qwen_plus", api_key_configured=True),
    )
    monkeypatch.setattr(
        "app.services.classification.orchestrator.LLMClient.probe",
        fake_probe,
    )

    llm_client = SequenceLLMClient([])
    llm_client.model_name = "gemini-2.5-flash-lite"
    orchestrator = ClassificationOrchestrator(llm_client=llm_client)

    asyncio.run(orchestrator._prepare_eu_dualuse_client())

    assert orchestrator._openrouter_client is llm_client


def test_v2_non_tangible_path_skips_generated_summary_and_uses_structured_fallback():
    document, pages = _sample_document_and_pages()
    llm_client = SequenceLLMClient(
        [
            _page_scan_payload(),
            _tangible_payload(item_identified=False, confidence=0.0),
        ],
        summary="HALLUCINATED SUMMARY THAT SHOULD NOT APPEAR",
    )
    orchestrator = ClassificationOrchestrator(llm_client=llm_client, eu_dualuse_client=llm_client)

    result = asyncio.run(orchestrator.classify_document(document, pages))

    assert llm_client.generate_text_calls == 0
    assert "HALLUCINATED SUMMARY" not in result["reasoning_summary"]
    assert "ne permet pas d'identifier clairement le bien, le logiciel, l'equipement ou l'element technique" in result["reasoning_summary"]
    assert "Aucun rattachement robuste a une categorie de controle n'a pu etre etabli" in result["reasoning_summary"]


def test_v2_fallback_summary_keeps_structured_audit_sections():
    summary = ClassificationOrchestrator._fallback_summary_v2(
        "FR_EC_Technical_Not_Controlled",
        0.85,
        False,
        [
            {
                "page_number": 1,
                "relevant": True,
                "content_signals": {"substantive": ["Tolérance H7/g6", "Programme A320"]},
            }
        ],
        step_results={
            "step_b": {
                "item_category": "outillage de production",
                "program_context": "A320",
            },
            "step_c": {
                "reasoning": "Aucun indice militaire determinent n'a ete releve.",
                "military_criteria_analysis": {
                    "nature": {"findings": "Outillage de chaine civile"},
                    "context": {"findings": "Programme Airbus A320"},
                },
                "exclusions_checked": ["ML10 note 1"],
            },
            "step_e": _unified_dualuse_not_controlled(),
        },
        tangible_description="Jeu de gabarits et outillages pour assemblage A320",
        lifecycle_phase="production",
    )

    assert "1. IDENTIFICATION DE L ELEMENT EXAMINE" in summary
    assert "2. ANALYSE MILITAIRE" in summary
    assert "3. ANALYSE DOUBLE USAGE" in summary
    assert "Categories analysees :" in summary
    assert "Rubriques verifiees :" in summary
    assert "5. DECISION ET ACTION" in summary


def test_coerce_summary_v2_rejects_sparse_freeform_text():
    orchestrator = ClassificationOrchestrator(llm_client=SequenceLLMClient([]))
    fallback = (
        "1. IDENTIFICATION DE L ELEMENT ANALYSE\n"
        "Nature : Outillage de production.\n"
        "Fonction : Gabarit civil.\n"
        "Contexte industriel : Programme A320.\n"
        "Elements techniques cites : Tolerances dimensionnelles.\n\n"
        "2. ANALYSE MILITAIRE\n"
        "Conclusion : Non militaire.\n"
        "Indices examines : Aucun indice militaire determinant.\n"
        "Exclusions retenues : ML10 note 1.\n\n"
        "3. ANALYSE DOUBLE USAGE\n"
        "Categories analysees : Categorie 2 examinee.\n"
        "Rubriques verifiees : 2B003 ecartee.\n"
        "Croisement Nature E : Aucune entree applicable.\n"
        "Conclusion : Non controle.\n\n"
        "4. ANALYSE TECHNIQUE DU DOCUMENT\n"
        "Ce que le document permet : Comprendre l'outillage civil.\n"
        "Ce qu il ne permet pas : Pas de reproduction d'un bien controle.\n"
        "Elements cites : Tolerances, references A320.\n\n"
        "5. DECISION ET ACTION\n"
        "Verdict propose : Document technique non controle.\n"
        "Action requise : Validation exploitable a ce stade sans revue supplementaire.\n"
        "Reserve eventuelle : Aucune reserve automatique majeure."
    )

    coerced = orchestrator._coerce_summary_v2(
        "Document civil standard, non militaire et non controle.",
        fallback=fallback,
        final_marking="FR_EC_Technical_Not_Controlled",
        requires_review=False,
    )

    assert coerced == fallback


def test_render_reasoning_summary_v2_rewrites_stale_military_dual_use_summary():
    step_results = {
        "step_b": {
            "item_identified": True,
            "program_context": "Defense",
        },
        "step_c": {
            "is_military": True,
            "reasoning": "Classification militaire retenue.",
            "military_criteria_analysis": {
                "nature": {"findings": "Composant de defense."},
            },
            "exclusions_checked": ["Aucune exclusion applicable."],
        },
        "step_d": _techdata_ml_payload(),
    }

    rendered = ClassificationOrchestrator.render_reasoning_summary_v2(
        (
            "1. IDENTIFICATION DE L ELEMENT EXAMINE\n\n"
            "2. ANALYSE MILITAIRE\n"
            "Conclusion : Classement militaire retenu.\n\n"
            "3. ANALYSE DOUBLE USAGE\n"
            "a. Categories analysees : Categorie 3.\n"
            "b. Rubriques verifiees : 3A225.\n"
            "c. Croisement Nature E : Non applicable.\n"
            "Conclusion : Non applicable au regime double usage."
        ),
        final_marking="FR_EC_ML22.A",
        final_confidence=0.91,
        requires_review=True,
        step_results=step_results,
        tangible_description="Tube electronique militaire",
        lifecycle_phase="production",
        page_payloads=[
            {
                "page_number": 1,
                "relevant": True,
                "content_signals": {
                    "substantive": [
                        "SpÃ©cification MIL-PRF-1/115M",
                        "Courant pulsÃ© 325 A",
                    ]
                },
                "tangible_hints": [{"name": "Thyratron 5C22"}],
            }
        ],
    )

    assert "3. ANALYSE DOUBLE USAGE" not in rendered
    assert "La qualification militaire a ete retenue comme regime principal" in rendered
    assert "Categorie 3." not in rendered
    assert rendered.count("Conclusion :") == 1
    assert "SpÃ©cification" not in rendered
