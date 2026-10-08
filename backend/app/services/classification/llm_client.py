from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
import re
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.classification.response_parser import ResponseParsingError, extract_json
from app.services.classification.runtime_config import get_runtime_profile

logger = logging.getLogger(__name__)

_RETRY_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_MAX_RETRIES = 2
_RATE_LIMIT_MAX_RETRIES = 6
_RETRY_BACKOFF_SECONDS = 3.0


class LLMRequestError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, *, profile_id: str | None = None) -> None:
        self.settings = get_settings()
        self.runtime = get_runtime_profile(profile_id)
        self.base_url = self.runtime.base_url.rstrip("/")
        self.model_name = self.runtime.model_name
        self.runtime_name = self.runtime.runtime_name
        self.image_transport = self.runtime.image_transport
        self.verify_ssl = self.runtime.verify_ssl
        self.step2_visual_thinking = self.runtime.step2_visual_thinking
        self.timeout_seconds = self.runtime.timeout_seconds
        self.max_tokens = self.runtime.max_tokens
        self.headers = self._build_headers()

    async def healthcheck(self) -> dict[str, Any]:
        self._ensure_runtime_ready()
        async with httpx.AsyncClient(timeout=20.0, verify=self.verify_ssl) as client:
            response = await client.get(f"{self.base_url}/models", headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def probe(self) -> tuple[bool, str]:
        """Quick availability check: send a tiny completion to verify the model accepts requests.

        Returns (ok, detail) where *ok* is True when the model responded
        successfully and *detail* contains an error description on failure.
        """
        try:
            self._ensure_runtime_ready()
        except LLMRequestError as exc:
            return False, str(exc)
        payload: dict[str, Any] = {
            "model": self.model_name,
            "temperature": 0.0,
            "seed": self.settings.llm_seed,
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "Say OK"}],
        }
        provider_options = self._build_provider_options()
        if provider_options is not None:
            payload["provider"] = provider_options
        try:
            async with httpx.AsyncClient(timeout=15.0, verify=self.verify_ssl) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                return True, "ok"
        except httpx.HTTPStatusError as exc:
            detail = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            logger.warning("Probe failed for %s — %s", self.model_name, detail)
            return False, detail
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            detail = f"{type(exc).__name__}: {exc}"
            logger.warning("Probe failed for %s — %s", self.model_name, detail)
            return False, detail
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            logger.warning("Probe failed for %s — %s", self.model_name, detail)
            return False, detail

    async def generate_json(self, prompt: str, *, image_path: str | None = None, thinking: bool = False) -> dict:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if image_path:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": self._build_image_url(Path(image_path))},
                }
            )

        response = await self._chat_completion(content=content, thinking=thinking, json_mode=True)
        try:
            return extract_json(response)
        except ResponseParsingError as exc:
            preview = self._format_response_preview(response)
            raise LLMRequestError(
                f"LLM response parsing failed: {exc}. Response preview: {preview}"
            ) from exc

    async def generate_text(self, prompt: str) -> str:
        content = [{"type": "text", "text": prompt}]
        return await self._chat_completion(content=content, thinking=False, json_mode=False)

    async def _chat_completion(self, *, content: list[dict[str, Any]], thinking: bool, json_mode: bool = False) -> str:
        self._ensure_runtime_ready()
        system_text = (
            "You are an export control analyst. Provide concise, auditable outputs only. "
            "Do not expose hidden reasoning. Think internally if needed but return only the requested format."
        )
        if thinking:
            system_text += " Spend extra internal effort on ambiguity and threshold analysis."
        if json_mode:
            system_text += " You MUST respond with a single valid JSON object. No text before or after."

        payload: dict[str, Any] = {
            "model": self.model_name,
            "temperature": self.settings.llm_temperature,
            "seed": self.settings.llm_seed,
            "max_tokens": self.max_tokens,
            "messages": self._build_messages(system_text=system_text, content=content),
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        provider_options = self._build_provider_options()
        if provider_options is not None:
            payload["provider"] = provider_options
        last_exc: Exception | None = None
        attempt = 0
        while True:
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds, verify=self.verify_ssl) as client:
                    response = await client.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload)
                    response.raise_for_status()
                    body = response.json()
                return self._extract_chat_content(body)
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = exc.response.status_code
                max_retries = self._max_retries_for_status(status)
                if status in _RETRY_STATUS_CODES and attempt < max_retries:
                    wait = self._retry_delay_for_http_error(exc, attempt)
                    logger.warning("LLM HTTP %d on attempt %d/%d - retrying in %.1fs", status, attempt + 1, max_retries + 1, wait)
                    attempt += 1
                    await asyncio.sleep(wait)
                    continue
                detail = self._format_http_error(exc)
                logger.error("%s after %d attempts - giving up", detail, attempt + 1)
                raise LLMRequestError(detail) from exc
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    wait = _RETRY_BACKOFF_SECONDS * (attempt + 1)
                    logger.warning("LLM %s on attempt %d/%d - retrying in %.1fs", type(exc).__name__, attempt + 1, _MAX_RETRIES + 1, wait)
                    attempt += 1
                    await asyncio.sleep(wait)
                    continue
                detail = self._format_transport_error(exc)
                logger.error("%s after %d attempts - giving up", detail, attempt + 1)
                raise LLMRequestError(detail) from exc
        raise last_exc  # type: ignore[misc]

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        api_key = (self.runtime.api_key or "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if self._uses_openrouter():
            # Required by OpenRouter for free-tier models.
            headers["HTTP-Referer"] = "https://veltar-classifier.local"
            headers["X-Title"] = "Veltar Classifier"
        return headers

    def _ensure_runtime_ready(self) -> None:
        if self._uses_openrouter() and not self.runtime.api_key_configured:
            raise LLMRequestError(
                "Runtime OpenRouter non configure. Renseignez OPENROUTER_API_KEY "
                "ou LLM_API_KEY avant de lancer une classification."
            )

    def _uses_openrouter(self) -> bool:
        return "openrouter.ai" in self.base_url.lower()

    def _build_provider_options(self) -> dict[str, Any] | None:
        """Return the OpenRouter `provider` routing block for deterministic requests.

        OpenRouter multiplexes providers per model; without constraints it may route the
        same request to different providers, which silently defeats `seed` and `temperature=0`.
        `require_parameters` forces routing only to providers that honor every param we send
        (notably `seed`), preserving reproducibility while still allowing fallback inside that
        qualified pool. An explicit `order` pins preference without sacrificing availability
        when `allow_fallbacks` is enabled.
        """
        if not self._uses_openrouter():
            return None
        options: dict[str, Any] = {
            "require_parameters": bool(self.settings.openrouter_require_parameters),
            "allow_fallbacks": bool(self.settings.openrouter_allow_provider_fallbacks),
        }
        order = [item for item in (self.settings.openrouter_provider_order or []) if item and item.strip()]
        if order:
            options["order"] = order
        return options

    @staticmethod
    def _format_http_error(exc: httpx.HTTPStatusError) -> str:
        status = exc.response.status_code
        body = exc.response.text.strip().replace("\n", " ")
        if body:
            return f"LLM HTTP {status}: {body[:500]}"
        return f"LLM HTTP {status}"

    @staticmethod
    def _format_transport_error(exc: Exception) -> str:
        detail = str(exc).strip()
        if detail:
            return f"LLM {type(exc).__name__}: {detail}"
        return f"LLM {type(exc).__name__}"

    @staticmethod
    def _retry_delay_for_http_error(exc: httpx.HTTPStatusError, attempt: int) -> float:
        fallback = _RETRY_BACKOFF_SECONDS * (attempt + 1)
        response = exc.response

        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return max(float(retry_after), fallback)
            except ValueError:
                pass

        body = response.text or ""
        match = re.search(r"Please retry in\s+([0-9]+(?:\.[0-9]+)?)\s*(ms|s)\b", body, flags=re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()
            seconds = value / 1000.0 if unit == "ms" else value
            return max(seconds, fallback)

        return fallback

    @staticmethod
    def _max_retries_for_status(status: int) -> int:
        if status == 429:
            return _RATE_LIMIT_MAX_RETRIES
        return _MAX_RETRIES

    @staticmethod
    def _format_response_preview(text: str, *, limit: int = 400) -> str:
        compact = " ".join(text.strip().split())
        if not compact:
            return "<empty response>"
        if len(compact) <= limit:
            return compact
        return compact[: limit - 3] + "..."

    @classmethod
    def _format_body_preview(cls, body: Any, *, limit: int = 400) -> str:
        try:
            text = str(body)
        except Exception:
            return "<unprintable response>"
        return cls._format_response_preview(text, limit=limit)

    @classmethod
    def _extract_chat_content(cls, body: Any) -> str:
        if not isinstance(body, dict):
            raise LLMRequestError(f"LLM response body is not a JSON object: {cls._format_body_preview(body)}")

        error = body.get("error")
        if error:
            if isinstance(error, dict):
                detail = error.get("message") or error.get("code") or cls._format_body_preview(error)
            else:
                detail = str(error)
            raise LLMRequestError(f"LLM provider returned an error payload: {detail}")

        choices = body.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0] or {}
            message = first_choice.get("message") if isinstance(first_choice, dict) else None
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    text_parts: list[str] = []
                    for item in content:
                        if not isinstance(item, dict):
                            continue
                        if item.get("type") in {"text", "output_text"} and isinstance(item.get("text"), str):
                            text_parts.append(item["text"])
                    joined = "\n".join(part for part in text_parts if part.strip()).strip()
                    if joined:
                        return joined

        output_text = body.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        raise LLMRequestError(f"LLM response missing choices/message content: {cls._format_body_preview(body)}")

    def _build_messages(self, *, system_text: str, content: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self._should_inline_system_prompt():
            return [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{system_text}\n\nFollow the user request below exactly."},
                        *content,
                    ],
                }
            ]
        return [
            {"role": "system", "content": system_text},
            {"role": "user", "content": content},
        ]

    def _should_inline_system_prompt(self) -> bool:
        model_name = self.model_name.lower()
        return "gemma-3" in model_name

    def _build_image_url(self, image_path: Path) -> str:
        if self.image_transport == "file_url":
            root = self.settings.llm_file_url_root.resolve()
            try:
                relative_path = image_path.resolve().relative_to(root)
            except ValueError as exc:
                raise ValueError(f"Image path '{image_path}' is outside configured LLM file root '{root}'.") from exc
            return f"file://{relative_path.as_posix()}"

        encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"
