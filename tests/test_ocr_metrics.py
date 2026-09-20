from tests.ocr_benchmark import edit_distance,error_rate,normalize_text
def test_edit_distance_known_case(): assert edit_distance('kitten','sitting')==3
def test_error_rate_exact_match_is_zero(): assert error_rate('ABC123','ABC123')==0.0
def test_word_normalization_collapses_whitespace_without_changing_case_or_punctuation(): assert normalize_text('  INV-102\n\n  Total: 11800.00  ',words=True)=='INV-102 Total: 11800.00'

def test_default_benchmark_output_cannot_overwrite_historical_baseline():
    from tests.ocr_benchmark import DEFAULT_OUTPUT
    assert DEFAULT_OUTPUT.name != 'baseline.json'
