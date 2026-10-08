from app.services.classification.response_parser import extract_json


def test_extract_json_repairs_missing_commas_between_properties():
    raw = """
    {
      "is_military": false
      "confidence": 0.12,
      "reasoning": "civil tooling"
    }
    """

    parsed = extract_json(raw)

    assert parsed["is_military"] is False
    assert parsed["confidence"] == 0.12
    assert parsed["reasoning"] == "civil tooling"


def test_extract_json_repairs_code_block_with_trailing_comma():
    raw = """
    ```json
    {
      "eccn": "2E003",
      "is_listed": true,
    }
    ```
    """

    parsed = extract_json(raw)

    assert parsed == {"eccn": "2E003", "is_listed": True}


def test_extract_json_repairs_truncated_string_and_closes_structures():
    raw = """
    {
      "is_listed": false,
      "eccn": null,
      "search_keywords_tried": [
        {"keyword": "CMM", "results": ["2B006 - Dimensional inspection systems"]},
        {"keyword": "dimensional inspection", "results": ["2B006 - Dimensional inspection/measuring systems
    """

    parsed = extract_json(raw)

    assert parsed["is_listed"] is False
    assert parsed["eccn"] is None
    assert len(parsed["search_keywords_tried"]) == 2
    assert parsed["search_keywords_tried"][1]["keyword"] == "dimensional inspection"


def test_extract_json_escapes_raw_newlines_inside_strings():
    raw = '{\n  "reasoning": "line 1\nline 2",\n  "is_listed": false\n}'

    parsed = extract_json(raw)

    assert parsed["is_listed"] is False
    assert parsed["reasoning"] == "line 1\nline 2"
