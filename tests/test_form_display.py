from app.utils.form_display import clean_optional_text, form_blank, form_finalize


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
    assert form_blank("NONE") == ""
    assert form_blank("none ") == ""
    assert form_blank("  ok  ") == "  ok  "


def test_form_finalize_for_template_output():
    assert form_finalize(None) == ""
    assert form_finalize("None") == ""
    assert form_finalize(" NONE ") == ""
    assert form_finalize("ok") == "ok"
    assert form_finalize(123) == 123
