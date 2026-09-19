from tests.ocr_benchmark import edit_distance, error_rate, normalize_text


def test_edit_distance_known_case() -> None:
    assert edit_distance("kitten", "sitting") == 3


def test_error_rate_exact_match_is_zero() -> None:
    assert error_rate("ABC123", "ABC123") == 0.0


def test_word_normalization_collapses_whitespace_without_changing_case_or_punctuation() -> None:
    assert normalize_text("  INV-102\n\n  Total: 11800.00  ", words=True) == "INV-102 Total: 11800.00"
