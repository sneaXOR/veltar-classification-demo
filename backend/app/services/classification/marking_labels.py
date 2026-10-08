from __future__ import annotations

import re

from app.services.language_settings import get_rationale_language, resolve_text

MARKING_CODE_PATTERN = re.compile(
    r"\b(?:EC_Not_Technical|EC_Review_Required|[A-Z]{2}_EC_[A-Za-z0-9_.]+|US_[A-Za-z0-9_.]+)\b"
)


def _humanize_suffix(value: str) -> str:
    parts = re.split(r"[_\s]+", value.strip())
    humanized: list[str] = []
    for part in parts:
        if not part:
            continue
        if re.fullmatch(r"[A-Z0-9.]+", part):
            humanized.append(part)
        else:
            humanized.append(part[:1].upper() + part[1:].lower())
    return " ".join(humanized) if humanized else value


def _country_marking_parts(code: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"([A-Z]{2})_EC_(.+)", code)
    if not match:
        return None
    return match.group(1), match.group(2)


def get_marking_label(code: str | None, *, language: str | None = None) -> str:
    selected_language = language or get_rationale_language()
    if not code:
        return "-"

    predefined_labels = {
        "EC_Not_Technical": resolve_text(
            english="Non-technical document",
            french="Document non technique",
            language=selected_language,
        ),
        "EC_Review_Required": resolve_text(
            english="Export classification to be confirmed",
            french="Classification export a confirmer",
            language=selected_language,
        ),
        "EU_EC_Technical_Not_Controlled": resolve_text(
            english="Technical document not controlled under EU dual-use rules",
            french="Document technique non controle (reglement UE double usage)",
            language=selected_language,
        ),
        "US_EAR99": resolve_text(
            english="Commercial item not controlled (EAR99)",
            french="Article commercial non controle (EAR99)",
            language=selected_language,
        ),
        "US_REVIEW_REQUIRED": resolve_text(
            english="US export classification to be confirmed",
            french="Classification export US a confirmer",
            language=selected_language,
        ),
    }
    if code in predefined_labels:
        return predefined_labels[code]

    country_marking = _country_marking_parts(code)
    if country_marking:
        country_code, suffix = country_marking
        if suffix.startswith("AMA"):
            return resolve_text(
                english=f"{country_code} export control - entry {suffix}",
                french=f"Controle export {country_code} - rubrique {suffix}",
                language=selected_language,
            )
        if suffix.startswith("ML"):
            return resolve_text(
                english=f"{country_code} export control - entry {suffix}",
                french=f"Controle export {country_code} - rubrique {suffix}",
                language=selected_language,
            )
        if suffix == "Technical_Not_Controlled":
            return resolve_text(
                english=f"Technical document not controlled ({country_code})",
                french=f"Document technique non controle ({country_code})",
                language=selected_language,
            )
        return resolve_text(
            english=f"{country_code} export control - entry {_humanize_suffix(suffix)}",
            french=f"Controle export {country_code} - rubrique {_humanize_suffix(suffix)}",
            language=selected_language,
        )

    if code.startswith("US_ITAR_"):
        return resolve_text(
            english=f"US ITAR - entry {_humanize_suffix(code.removeprefix('US_ITAR_'))}",
            french=f"ITAR Etats-Unis - rubrique {_humanize_suffix(code.removeprefix('US_ITAR_'))}",
            language=selected_language,
        )
    if code.startswith("US_EAR_"):
        return resolve_text(
            english=f"US EAR - entry {_humanize_suffix(code.removeprefix('US_EAR_'))}",
            french=f"EAR Etats-Unis - rubrique {_humanize_suffix(code.removeprefix('US_EAR_'))}",
            language=selected_language,
        )
    if code.startswith("US_"):
        return resolve_text(
            english=f"US export control - {_humanize_suffix(code.removeprefix('US_'))}",
            french=f"Controle export Etats-Unis - {_humanize_suffix(code.removeprefix('US_'))}",
            language=selected_language,
        )
    return _humanize_suffix(code)


def replace_marking_codes_in_text(text: str | None, *, language: str | None = None) -> str:
    if not text:
        return ""
    return MARKING_CODE_PATTERN.sub(lambda match: get_marking_label(match.group(0), language=language), text)
