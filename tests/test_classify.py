"""Tests for pipeline/classify.py's tool schema consistency."""

from typing import get_args, get_type_hints

from pipeline.classify import _TOOL, ClassificationResult, LetterCategory, ScamType


def test_tool_schema_fields_match_classification_result():
    schema_fields = set(_TOOL["input_schema"]["properties"])
    result_fields = set(get_type_hints(ClassificationResult))
    assert schema_fields == result_fields


def test_tool_schema_category_enum_matches_literal():
    schema_enum = set(_TOOL["input_schema"]["properties"]["category"]["enum"])
    literal_values = set(get_args(LetterCategory))
    assert schema_enum == literal_values


def test_tool_schema_scam_type_enum_matches_literal():
    schema_enum = set(_TOOL["input_schema"]["properties"]["scam_type"]["enum"])
    literal_values = set(get_args(ScamType))
    assert schema_enum == literal_values


def test_scam_type_is_required_alongside_category_and_image_quality():
    # scam_type is a second, orthogonal axis (like image_quality), not a
    # gate - it must always be requested from the model, never optional,
    # so `not_applicable` is a real returned value rather than a missing key.
    assert "scam_type" in _TOOL["input_schema"]["required"]
