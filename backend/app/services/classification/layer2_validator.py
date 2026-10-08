from __future__ import annotations

import re
from statistics import mean

from app.core.config import get_settings
from app.models.enums import ReviewPriority


MARKING_PATTERNS = [
    r"^EC_Not_Technical$",
    r"^[A-Z]{2}_EC_(?:ML\d{1,2}(?:\.[A-Za-z0-9]+)?|AMA[1-4]|[0-9][A-E][0-9]{3}|Technical_Not_Controlled)$",
    r"^US_(?:ITAR_[A-Za-z0-9]+|EAR_[0-9][A-E][0-9]{3}|EAR99|REVIEW_REQUIRED)$",
    r"^EC_Review_Required$",
]

TECHNICAL_NOT_CONTROLLED_PATTERN = re.compile(r"^[A-Z]{2}_EC_Technical_Not_Controlled$")


class Layer2Validator:
    def __init__(self) -> None:
        self.settings = get_settings()

    def validate_marking_format(self, marking: str) -> bool:
        return any(re.match(pattern, marking) for pattern in MARKING_PATTERNS)

    @staticmethod
    def is_technical_not_controlled_marking(marking: str | None) -> bool:
        return bool(marking and TECHNICAL_NOT_CONTROLLED_PATTERN.match(marking))

    def validate_coherence(self, payload: dict) -> tuple[bool, list[str]]:
        errors: list[str] = []
        technical = payload.get("step2", {}).get("is_technical")
        military = payload.get("step5", {}).get("is_military")
        dual_use = payload.get("step7", {}).get("is_listed")
        if technical is False and (military or dual_use):
            errors.append("A non-technical document cannot be military or dual-use controlled.")
        if military and dual_use:
            errors.append("Military and dual-use determinations cannot both be final.")
        marking = payload.get("final_marking")
        if marking and not self.validate_marking_format(marking):
            errors.append(f"Invalid marking format: {marking}")
        return not errors, errors

    def validate_coherence_v2(self, payload: dict) -> tuple[bool, list[str]]:
        """V2 coherence checks aligned with expert methodology."""
        errors: list[str] = []
        warnings: list[str] = []

        step_b = payload.get("step_b", {})
        step_c = payload.get("step_c", {})
        step_d = payload.get("step_d", {})
        step_e = payload.get("step_e", {})
        step_f = payload.get("step_f", {})
        marking = payload.get("final_marking")

        tangible_identified = step_b.get("item_identified", False)
        is_military = step_c.get("is_military", False)
        is_dual_listed = step_e.get("is_listed", False)

        # Detect US lane from marking prefix
        is_us_lane = bool(marking and (marking.startswith("US_") or marking == "US_EAR99"))

        if not is_us_lane and is_military and is_dual_listed:
            errors.append("Military and dual-use determinations cannot both be final.")

        if not tangible_identified and marking and marking not in ("EC_Not_Technical", "US_EAR99"):
            errors.append("No tangible identified but marking is not EC_Not_Technical or US_EAR99.")

        # FR/EU-specific coherence checks (don't apply to US lane)
        if (
            not is_us_lane
            and is_military
            and step_d
            and not step_d.get("is_technical_data")
            and marking
            and marking not in ("EC_Not_Technical", "EC_Review_Required")
        ):
            errors.append("Military tangible but document is not technical data - expected EC_Not_Technical.")

        if (
            not is_us_lane
            and is_dual_listed
            and step_f
            and not step_f.get("is_technical_data")
            and marking
            and marking not in ("EC_Not_Technical", "EC_Review_Required")
            and not self.is_technical_not_controlled_marking(marking)
        ):
            errors.append(
                "Dual-use tangible listed but document is not controlled technical data - expected "
                "EC_Not_Technical, *_EC_Technical_Not_Controlled, or EC_Review_Required."
            )

        if marking and not self.validate_marking_format(marking):
            errors.append(f"Invalid marking format: {marking}")

        if tangible_identified and not step_b.get("_llm_failed"):
            if not is_military and not step_e:
                warnings.append("Tangible non-militaire identifie mais step_e (dual-use) absent.")
            if is_military and not step_d:
                warnings.append("Tangible militaire identifie mais step_d (ML22) absent.")
            if is_dual_listed and not step_f:
                warnings.append("Tangible dual-use liste mais step_f (Nature E) absent.")

        eccn = step_e.get("eccn")
        if eccn and not re.match(r"^\d[A-E]\d{3}$", str(eccn)):
            warnings.append(f"ECCN '{eccn}' ne respecte pas le format attendu (ex: 2B001).")

        final_conf = payload.get("final_confidence", 0.0)
        if isinstance(final_conf, (int, float)) and final_conf < 0.15:
            warnings.append("Confiance finale tres basse (<15%) - resultats peu fiables.")

        for step_key in ("step_b", "step_c", "step_d", "step_e", "step_f"):
            step = payload.get(step_key, {})
            if step.get("_llm_failed") and marking and marking != "EC_Review_Required":
                errors.append(f"{step_key} a echoue mais le marking final n'est pas EC_Review_Required.")

        lifecycle_phase = step_b.get("lifecycle_phase", "")
        if lifecycle_phase and "modification" in str(lifecycle_phase).lower():
            warnings.append("Phase modification detected - technology type may be 'development' despite use context.")

        if lifecycle_phase and any(kw in str(lifecycle_phase).lower() for kw in ("assemblage", "integration", "assembly")):
            warnings.append("Assembly/integration phase - classification may differ at system level.")

        return not errors, errors + warnings

    def compute_final_confidence(self, step_confidences: list[float]) -> float:
        if not step_confidences:
            return 0.0
        return round(mean(step_confidences), 4)

    def determine_review_priority(
        self,
        confidence: float,
        *,
        insufficient_evidence: bool,
        experimental: bool,
        has_threshold_borderline: bool,
    ) -> ReviewPriority:
        if experimental or insufficient_evidence:
            return ReviewPriority.HIGH
        if has_threshold_borderline or confidence < self.settings.review_confidence_threshold:
            return ReviewPriority.MEDIUM
        return ReviewPriority.LOW

    def should_require_review(self, confidence: float, *, experimental: bool, insufficient_evidence: bool) -> bool:
        return experimental or insufficient_evidence or confidence < self.settings.review_confidence_threshold

    def detect_insufficient_evidence(self, page_payloads: list[dict], step_payloads: list[dict]) -> bool:
        low_signal_pages = [
            payload for payload in page_payloads if payload.get("confidence", 0.0) < self.settings.insufficient_evidence_threshold
        ]
        explicit_gaps = [
            payload
            for payload in page_payloads + step_payloads
            if payload.get("missing_information") or payload.get("uncertainties")
        ]
        return len(low_signal_pages) == len(page_payloads) or len(explicit_gaps) > 2

    @staticmethod
    def threshold_borderline(thresholds: list[dict]) -> bool:
        numeric_pattern = re.compile(r"-?\d+(?:\.\d+)?")
        for threshold in thresholds:
            doc_value = threshold.get("document_value", "")
            threshold_value = threshold.get("threshold", "")
            doc_match = numeric_pattern.search(str(doc_value))
            th_match = numeric_pattern.search(str(threshold_value))
            if not doc_match or not th_match:
                continue
            doc_number = float(doc_match.group(0))
            threshold_number = float(th_match.group(0))
            if threshold_number == 0:
                continue
            ratio = abs(doc_number - threshold_number) / abs(threshold_number)
            if ratio <= get_settings().close_to_threshold_ratio:
                return True
        return False
