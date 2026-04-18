"""工序快照文本：禁止将 None 写成字面量 'None'。"""

from app.services import production_svc as ps


def test_wo_op_snapshot_text_not_null_empty_for_none():
    assert ps._wo_op_snapshot_text_not_null(None, max_len=128) == ""
    assert ps._wo_op_snapshot_text_not_null("  ", max_len=128) == ""


def test_wo_op_snapshot_text_not_null_trims_and_truncates():
    assert ps._wo_op_snapshot_text_not_null("  铣削  ", max_len=128) == "铣削"
    long_s = "a" * 200
    assert len(ps._wo_op_snapshot_text_not_null(long_s, max_len=128)) == 128


def test_wo_op_snapshot_optional_code_none_for_missing():
    assert ps._wo_op_snapshot_optional_code(None, max_len=64) is None
    assert ps._wo_op_snapshot_optional_code("", max_len=64) is None
    assert ps._wo_op_snapshot_optional_code("  ", max_len=64) is None


def test_wo_op_snapshot_optional_code_keeps_value():
    assert ps._wo_op_snapshot_optional_code(" S01 ", max_len=64) == "S01"
