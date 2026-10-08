from __future__ import annotations

import ast
import json
import re


class ResponseParsingError(ValueError):
    """Raised when the model output cannot be parsed."""


def extract_json(text: str) -> dict:
    last_error: str | None = None
    for candidate in _candidate_json_strings(text):
        parsed, error = _parse_json_candidate(candidate)
        if parsed is not None:
            return parsed
        if error:
            last_error = error

    if last_error:
        raise ResponseParsingError(last_error)
    raise ResponseParsingError("No JSON object found in model response.")


def _candidate_json_strings(text: str) -> list[str]:
    stripped = text.strip()
    candidates: list[str] = []
    if stripped:
        candidates.append(stripped)

    for match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE):
        candidates.append(match.group(1).strip())

    candidates.extend(_extract_balanced_objects(stripped))
    return _dedupe_candidates(candidates)


def _extract_balanced_objects(text: str) -> list[str]:
    objects: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escape = False

    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(text[start:index + 1].strip())
                start = None

    return objects


def _dedupe_candidates(candidates: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


def _parse_json_candidate(candidate: str) -> tuple[dict | None, str | None]:
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None, None
    except json.JSONDecodeError as exc:
        last_error = str(exc)

    repaired = _repair_json(candidate)
    if repaired != candidate:
        try:
            parsed = json.loads(repaired)
            return parsed if isinstance(parsed, dict) else None, None
        except json.JSONDecodeError as exc:
            last_error = str(exc)

    pythonish = repaired
    pythonish = re.sub(r"\btrue\b", "True", pythonish)
    pythonish = re.sub(r"\bfalse\b", "False", pythonish)
    pythonish = re.sub(r"\bnull\b", "None", pythonish)
    try:
        parsed = ast.literal_eval(pythonish)
    except (SyntaxError, ValueError) as exc:
        return None, str(exc) or last_error

    if isinstance(parsed, dict):
        return parsed, None
    return None, last_error


def _repair_json(candidate: str) -> str:
    repaired = candidate.strip().lstrip("\ufeff")
    repaired = repaired.translate(
        str.maketrans(
            {
                "“": '"',
                "”": '"',
                "„": '"',
                "‟": '"',
                "’": "'",
                "‘": "'",
                "‚": "'",
                "‛": "'",
            }
        )
    )
    repaired = re.sub(r"^```(?:json)?\s*|\s*```$", "", repaired, flags=re.IGNORECASE | re.DOTALL)
    repaired = _escape_raw_newlines_in_strings(repaired)
    repaired = _close_unterminated_json_structures(repaired)
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    repaired = _insert_missing_commas_between_properties(repaired)
    return repaired.strip()


def _insert_missing_commas_between_properties(text: str) -> str:
    pattern = re.compile(
        r'("(?:\\.|[^"\\])*"|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\}|\])(\s+)(?="(?:\\.|[^"\\])*"\s*:)',
        flags=re.MULTILINE,
    )
    updated = text
    while True:
        next_value, count = pattern.subn(r"\1,\2", updated)
        if count == 0:
            return next_value
        updated = next_value


def _escape_raw_newlines_in_strings(text: str) -> str:
    output: list[str] = []
    in_string = False
    escape = False

    for char in text:
        if in_string:
            if escape:
                output.append(char)
                escape = False
                continue
            if char == "\\":
                output.append(char)
                escape = True
                continue
            if char == '"':
                output.append(char)
                in_string = False
                continue
            if char == "\n":
                output.append("\\n")
                continue
            if char == "\r":
                output.append("\\r")
                continue
            output.append(char)
            continue

        output.append(char)
        if char == '"':
            in_string = True
            escape = False

    return "".join(output)


def _close_unterminated_json_structures(text: str) -> str:
    output: list[str] = []
    stack: list[str] = []
    in_string = False
    escape = False

    for char in text:
        output.append(char)
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char in "{[":
            stack.append(char)
            continue
        if char == "}" and stack and stack[-1] == "{":
            stack.pop()
            continue
        if char == "]" and stack and stack[-1] == "[":
            stack.pop()

    if in_string:
        output.append('"')

    closers = {"{": "}", "[": "]"}
    while stack:
        output.append(closers[stack.pop()])

    return "".join(output)
