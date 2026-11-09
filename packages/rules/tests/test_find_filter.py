"""찾기 조건(FIND-03) — 경매·공매가 같은 값 이름, 값은 모두 바인딩."""

from datetime import date

from aucs_rules.find_filter import court_where, onbid_where, usage_re

D = date(2026, 11, 8)


def test_court_where_binds_everything() -> None:
    sql, p = court_where(
        {"sigungu": ["강남구"], "max_cash": 30_000_000, "usage": ["apt", "villa", "zzz"],
         "failed_min": 1, "rate_max": 70, "days_max": 14, "exclude": ["share", "fatal"], "q": "푸르지오"},
        D,
    )  # fmt: skip
    assert "any(%(sigungu)s)" in sql and p["max_cash"] == 30_000_000
    assert p["usage_re"] == "(아파트)|(다세대|연립|빌라)"
    assert p["ex_rules"] == ["risk.share"] and "'fatal'" in sql
    assert p["q"] == "%푸르지오%" and "푸르지오" not in sql


def test_empty_values_are_ignored() -> None:
    assert court_where({"sigungu": [], "max_cash": None, "usage": []}, D) == ("", {"today": D})


def test_onbid_uses_same_names() -> None:
    f = {"sigungu": ["수원시"], "max_cash": 5000, "usage": ["apt"], "exclude": ["share"]}
    _, p = court_where(f, D)
    sql = onbid_where(f)
    assert sql is not None
    for name in ("sigungu", "max_cash", "usage_re"):
        assert f"%({name})s" in sql and name in p
    assert "split_part(o.sigungu" in sql and "o.kind <> 'trust'" in sql
    assert onbid_where({"source": "court"}) is None and onbid_where({"court": ["B000210"]}) is None


def test_usage_re() -> None:
    assert usage_re(["zzz"]) is None and usage_re(["officetel"]) == "(오피스텔)"


def test_kind_sql_matches_card_kind() -> None:
    """11/9: 「오피스텔」로 찾으면 「상가,오피스텔,근린시설」이 섞였음 — 찾기 종류 = 카드 종류."""
    import re

    from aucs_rules.find_filter import kind_sql
    from aucs_rules.pick import usage_kind

    sql = kind_sql("u")
    whens = re.findall(r"~ '([^']+)' then '(\w+)'", sql)

    def by_sql(u: str) -> str:
        return next((k for pat, k in whens if re.search(pat, u)), "etc")

    for u in [
        "아파트",
        "상가,오피스텔,근린시설",
        "오피스텔",
        "다세대",
        "단독주택",
        "근린시설",
        "대지",
        "공장",
    ]:
        assert by_sql(u) == usage_kind(u), u
    sql2, p = court_where({"usage": ["officetel"], "max_cash": 1, "homes": 2}, D)
    assert p["kinds"] == ["officetel"] and p["homes_key"] == "2" and "cash_need" in sql2
