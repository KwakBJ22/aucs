import json

from aucs_workers.jobs.data_check import note_misses
from aucs_workers.ops_watch import data_lights


def test_note_misses():
    rows = [
        ("a", "농지취득자격증명 제출 필요(미제출시 보증금 몰수)", ["risk.permit_exempt"]),
        ("b", "농지취득자격증명 제출 필요", ["risk.farmland"]),
        ("c", "주택도시보증공사의 대항력 포기조건 매각", ["risk.prior_rights"]),
        ("d", "", []),
    ]
    assert note_misses(rows) == ["a"]


def test_data_lights():
    msg = {"list_diff": {"n": 3, "ex": []}, "note_signal": {"n": 2, "ex": ["x", "y"]},
           "soon_docs": {"n": 300, "ex": []}, "stale": {"n": 0, "ex": []}}  # fmt: skip
    keys = {r["key"] for r in data_lights({"message": json.dumps(msg)})}
    assert keys == {"data:note_signal", "data:soon_docs"}
    assert data_lights(None) == []
    assert data_lights({"message": "x"}) == []
