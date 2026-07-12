"""Tests for pipeline/classify.py's tool schema consistency."""

from typing import get_args, get_type_hints

from pipeline.classify import _TOOL, ClassificationResult, LetterCategory


def test_tool_schema_fields_match_classification_result():
    schema_fields = set(_TOOL["input_schema"]["properties"])
    result_fields = set(get_type_hints(ClassificationResult))
    assert schema_fields == result_fields


def test_tool_schema_category_enum_matches_literal():
    schema_enum = set(_TOOL["input_schema"]["properties"]["category"]["enum"])
    literal_values = set(get_args(LetterCategory))
    assert schema_enum == literal_values
