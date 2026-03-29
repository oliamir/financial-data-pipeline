"""Unit tests for JSON fix utilities."""

import pytest

from src.utils.json_fix import fix_json_numbers, extract_json_from_response, clean_numeric_value


class TestFixJsonNumbers:
    def test_accounting_notation(self):
        result = fix_json_numbers('{"loss": (1,234)}')
        assert "-1234" in result

    def test_comma_separated_numbers(self):
        result = fix_json_numbers('{"revenue": 43,536}')
        assert "43536" in result

    def test_large_comma_number(self):
        result = fix_json_numbers('{"assets": 1,234,567,890}')
        assert "1234567890" in result

    def test_negative_comma_number(self):
        result = fix_json_numbers('{"loss": -43,536}')
        assert "-43536" in result

    def test_no_change_for_valid_json(self):
        result = fix_json_numbers('{"revenue": 43536}')
        assert result == '{"revenue": 43536}'

    def test_javascript_comment_removal(self):
        result = fix_json_numbers('{"revenue": 100 // in thousands}')
        assert "//" not in result

    def test_trailing_comma(self):
        result = fix_json_numbers('{"a": 1, "b": 2,}')
        assert result == '{"a": 1, "b": 2}'


class TestExtractJsonFromResponse:
    def test_clean_json(self):
        result = extract_json_from_response('{"revenue": 100}')
        assert result == {"revenue": 100}

    def test_markdown_json_fence(self):
        response = '```json\n{"revenue": 100}\n```'
        result = extract_json_from_response(response)
        assert result == {"revenue": 100}

    def test_markdown_fence(self):
        response = 'Here is the data:\n```\n{"revenue": 100}\n```\nDone.'
        result = extract_json_from_response(response)
        assert result == {"revenue": 100}

    def test_surrounding_text(self):
        response = 'I found the following:\n{"revenue": 43,536}\nLet me know if you need more.'
        result = extract_json_from_response(response)
        assert result == {"revenue": 43536}

    def test_accounting_notation_in_response(self):
        response = '{"loss": (5,000), "revenue": 10,000}'
        result = extract_json_from_response(response)
        assert result["loss"] == -5000
        assert result["revenue"] == 10000

    def test_invalid_json_returns_none(self):
        result = extract_json_from_response("This is not JSON at all")
        assert result is None


class TestCleanNumericValue:
    def test_int(self):
        assert clean_numeric_value(42) == 42.0

    def test_float(self):
        assert clean_numeric_value(3.14) == 3.14

    def test_string_with_commas(self):
        assert clean_numeric_value("1,234,567") == 1234567.0

    def test_string_with_spaces(self):
        assert clean_numeric_value("  100  ") == 100.0

    def test_percentage(self):
        assert clean_numeric_value("25.5%") == 25.5

    def test_accounting_notation(self):
        assert clean_numeric_value("(1,234)") == -1234.0

    def test_none(self):
        assert clean_numeric_value(None) is None

    def test_non_numeric_string(self):
        assert clean_numeric_value("N/A") is None
