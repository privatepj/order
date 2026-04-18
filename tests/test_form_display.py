from app.utils.form_display import clean_optional_text, form_blank


def test_clean_optional_text_none_sentinel():
    assert clean_optional_text(None) is None
    assert clean_optional_text("") is None
    assert clean_optional_text("  ") is None
    assert clean_optional_text("None") is None
    assert clean_optional_text(" none ") is None
    assert clean_optional_text("  PCS  ") == "PCS"


def test_clean_optional_text_max_len():
    assert clean_optional_text("abcd", max_len=2) == "ab"


def test_form_blank_for_template():
    assert form_blank(None) == ""
    assert form_blank("None") == ""
    assert form_blank("none ") == ""
    assert form_blank("  ok  ") == "  ok  "
