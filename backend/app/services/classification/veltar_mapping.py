from __future__ import annotations

import re


VELTAR_MAPPING_VERSION = "2026.03"


def project_to_veltar(marking: str, *, experimental: bool, confidence: float) -> dict:
    payload = {
        "version": VELTAR_MAPPING_VERSION,
        "internal_marking": marking,
        "confidence": confidence,
        "experimental": experimental,
        "classification_code": None,
        "jurisdictions": [],
        "eccn_scope": [],
        "nature": None,
        "is_controlled": True,
    }
    if marking == "EC_Not_Technical":
        payload.update({"classification_code": "PUBLIC", "jurisdictions": ["PUBLIC"], "nature": "civil", "is_controlled": False})
        return payload
    if marking == "EC_Review_Required":
        payload.update({"classification_code": "INTERNAL", "jurisdictions": ["INTERNAL"], "nature": "civil", "is_controlled": False})
        return payload
    generic_match = re.match(r"^([A-Z]{2})_EC_(.+)$", marking)
    if generic_match:
        country_code = generic_match.group(1)
        suffix = generic_match.group(2)
        if suffix.startswith("AMA"):
            payload.update({"classification_code": suffix, "jurisdictions": [f"{country_code}-ML"], "nature": "military"})
            return payload
        if suffix.startswith("ML"):
            match = re.match(r"(ML\d{1,2})(?:\.(.+))?$", suffix)
            base = match.group(1) if match else "ML"
            detail = match.group(2) if match and match.group(2) else ""
            payload.update(
                {
                    "classification_code": f"{base}{detail[:1].upper()}" if detail else base,
                    "jurisdictions": [f"{country_code}-ML"],
                    "eccn_scope": [suffix],
                    "nature": "military",
                }
            )
            return payload
        payload.update(
            {
                "classification_code": f"{country_code}-DU",
                "jurisdictions": [f"{country_code}-DU"],
                "eccn_scope": [suffix],
                "nature": "civil",
                "is_controlled": suffix != "Technical_Not_Controlled",
            }
        )
        return payload
    if marking.startswith("FR_EC_AMA"):
        payload.update({"classification_code": marking.removeprefix("FR_EC_"), "jurisdictions": ["FR-ML"], "nature": "military"})
        return payload
    if marking.startswith("FR_EC_ML"):
        match = re.match(r"FR_EC_(ML\d{1,2})(?:\.(.+))?$", marking)
        base = match.group(1) if match else "ML"
        suffix = match.group(2) if match and match.group(2) else ""
        payload.update(
            {
                "classification_code": f"{base}{suffix[:1].upper()}-FR" if suffix else f"{base}-FR",
                "jurisdictions": ["FR-ML"],
                "eccn_scope": [marking.removeprefix("FR_EC_")],
                "nature": "military",
            }
        )
        return payload
    if marking.startswith("EU_EC_"):
        payload.update(
            {
                "classification_code": "EU-DU",
                "jurisdictions": ["EU-DU"],
                "eccn_scope": [marking.removeprefix("EU_EC_")],
                "nature": "civil",
                "is_controlled": marking != "EU_EC_Technical_Not_Controlled",
            }
        )
        return payload
    if marking.startswith("US_ITAR_"):
        payload.update(
            {
                "classification_code": "ITAR",
                "jurisdictions": ["ITAR"],
                "eccn_scope": [marking.removeprefix("US_ITAR_")],
                "nature": "military",
            }
        )
        return payload
    if marking == "US_EAR99":
        payload.update(
            {
                "classification_code": "EAR99",
                "jurisdictions": ["EAR"],
                "eccn_scope": ["EAR99"],
                "nature": "civil",
                "is_controlled": False,
            }
        )
        return payload
    if marking.startswith("US_EAR_"):
        eccn = marking.removeprefix("US_EAR_")
        payload.update(
            {
                "classification_code": "EAR" if eccn != "EAR99" else "EAR99",
                "jurisdictions": ["EAR"],
                "eccn_scope": [eccn],
                "nature": "civil",
                "is_controlled": eccn != "EAR99",
            }
        )
        return payload
    if marking == "US_REVIEW_REQUIRED":
        payload.update({"classification_code": "INTERNAL", "jurisdictions": ["EAR"], "nature": "civil", "is_controlled": False})
        return payload
    return payload
