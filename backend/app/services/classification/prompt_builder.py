from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.services.language_settings import (
    get_analysis_language,
    get_prompt_language_name,
    get_rationale_language,
    resolve_text,
)


class PromptBuilder:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.root = Path(self.settings.prompts_root)

    def build(
        self,
        template_name: str,
        *,
        kb_block: str,
        document_block: str,
        filename: str = "",
        lane: str = "",
        client_context: str = "",
    ) -> str:
        resolved_template_name, output_language = self._resolve_template_name(template_name)
        template = (self.root / resolved_template_name).read_text(encoding="utf-8")
        prompt = template.format(
            kb_block=kb_block,
            document_block=document_block,
            filename=filename,
            lane=lane,
            client_context=client_context or self._default_client_context(output_language),
        )
        if resolved_template_name.startswith("layer3_summary"):
            return prompt
        return f"{prompt.rstrip()}\n\n{self._language_instruction(output_language)}\n"

    @staticmethod
    def _default_client_context(language: str) -> str:
        return resolve_text(
            english="No client context available.",
            french="Aucun contexte client disponible.",
            language=language,
        )

    @staticmethod
    def _language_instruction(language: str) -> str:
        language_name = get_prompt_language_name(language)
        return "\n".join(
            [
                "OUTPUT LANGUAGE REQUIREMENTS",
                f"- Write every natural-language sentence in {language_name}.",
                "- Keep JSON keys, enum values, booleans, and numeric values exactly as requested.",
                f"- Every summary, reasoning string, evidence reason, page summary, and missing-information sentence must be in {language_name}.",
            ]
        )

    @staticmethod
    def _resolve_template_name(template_name: str) -> tuple[str, str]:
        if template_name.startswith("layer3_summary"):
            rationale_language = get_rationale_language()
            if rationale_language == "en":
                return template_name.replace(".txt", "_en.txt"), rationale_language
            return template_name, rationale_language
        return template_name, get_analysis_language()
