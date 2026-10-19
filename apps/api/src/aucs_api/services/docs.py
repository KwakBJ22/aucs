"""DOC-01 원문 보기: 법원에서 받은 현황조사서·문건송달내역·매각물건명세서를 읽기 쉽게 (감정평가서는 보이지 않음).

원문 글은 고치지 않고 줄바꿈 태그만 정리합니다. 사람 이름은 법원이 이미 가린 것 외에 임차인 이름도 가립니다.
"""

import re
from datetime import datetime
from typing import Any

from aucs_workers.extract.mask import mask_names

from aucs_api.db import connect

# 손님이 꼭 봐야 하는 문건 (배당·권리·정지·점유)
_KEY = re.compile(
    r"(배당요구|권리신고|유치권|정지|취하|취소|회생|파산|채권계산서|임차인|점유|이의|항고|경매신청)"
)
_HIDE = re.compile(r"감정평가")


def _clean(s: Any) -> str | None:
    if not s:
        return None
    t = re.sub(r"<br\s*/?>", "\n", str(s)).strip()
    return t or None


def _ymd(s: Any) -> str | None:
    s = str(s or "")
    m = re.match(r"(\d{4})\.?(\d{2})\.?(\d{2})", s)
    return f"{m[1]}-{m[2]}-{m[3]}" if m else None


def _mask(name: Any) -> str | None:
    n = str(name or "").strip()
    if re.fullmatch(r"[가-힣]{2,4}", n):
        return n[0] + "○" * (len(n) - 1)
    return n or None


def status_report(p: dict[str, Any]) -> dict[str, Any]:
    """현황조사서 → 조사일·현황·점유·임대차 글·임차인 목록."""
    m = p.get("dma_curstExmnMngInf") or {}
    objs = p.get("dlt_ordTsRlet") or []
    lessees = p.get("dlt_ordTsLserLtn") or []
    return {
        "exam_at": _clean(m.get("exmnDtDts")),
        "summary": _clean(m.get("printRltnDts")),
        "lease_note": _clean(m.get("lesDts")),
        "possession": [x for x in (mask_text(_clean(o.get("gdsPossCtt"))) for o in objs) if x],
        "tenants": [
            {
                "name": _mask(t.get("intrpsNm")),
                "part": _clean(t.get("lesPartCtt")),
                "use": _clean(t.get("lesUsgDts")),
                "move_in": _clean(t.get("mvinDtlCtt")),
                "fixed": _clean(t.get("rgstryCrtcpCfmtnCtt")),
                "deposit": _clean(t.get("lesDposDts")),
                "rent": _clean(t.get("mmrntAmtDts")),
                "note": mask_text(_clean(t.get("lesDtsRmk"))),
            }
            for t in lessees
        ],
    }


def deliveries(p: dict[str, Any]) -> dict[str, Any]:
    """문건·송달내역 → 접수 문건(중요 표시)과 송달."""
    filings: list[dict[str, Any]] = [
        {"date": _ymd(x.get("ofdocRcptYmd")), "text": _clean(x.get("rcptDts")), "result": _clean(x.get("rcptRslt"))}
        for x in p.get("dlt_ofdocDtsLst") or []
        if x.get("rcptDts")
    ]  # fmt: skip
    for f in filings:
        f["key"] = bool(_KEY.search(f["text"] or ""))
        if _HIDE.search(f["text"] or ""):
            f["text"] = "감정인 서류 제출"
    sends = [
        {"date": _ymd(x.get("dlvrbkRegYmd")), "text": _clean(x.get("dlvrDts")), "result": _clean(x.get("lastDlvrblRchYmd"))}
        for x in p.get("dlt_dlvrDtsLst") or []
        if x.get("dlvrDts")
    ]  # fmt: skip
    for s in sends:
        if _HIDE.search(s["text"] or ""):
            s["text"] = "감정인 송달"
    return {"filings": filings, "sends": sends}


_SHARE_OWNER = re.compile(r"(?<![가-힣])([가-힣])([가-힣]{1,3})(?=\s*(?:의\s*)?지분)")
_NOT_OWNER = {
    "공유",
    "전체",
    "일부",
    "토지",
    "건물",
    "대지",
    "해당",
    "나머지",
    "채무자",
    "소유자",
    "공유자",
    "각",
}


def mask_text(text: str | None) -> str | None:
    """원문 글의 사람 이름 가림: 역할 뒤 이름(mask_names) + 「홍길동 지분」 꼴."""
    if not text:
        return None
    t = mask_names(text)
    t = _SHARE_OWNER.sub(
        lambda m: m.group(0) if m.group(0) in _NOT_OWNER else m.group(1) + "○" * len(m.group(2)), t
    )
    return t


def spec_sheet(p: dict[str, Any]) -> dict[str, Any] | None:
    """물건상세의 명세서 묶음(dspslGdsDxdyInfo) → 작성일·최선순위·인수 권리·지상권·비고. 작성 전이면 None."""
    info = (p.get("dma_result") or {}).get("dspslGdsDxdyInfo") or {}
    if not info.get("gdsSpcfcWrtYmd"):
        return None

    def t(k: str) -> str | None:
        return mask_text(_clean(info.get(k)))

    remark, item_remark = t("gdsSpcfcRmk"), t("dspslGdsRmk")
    if item_remark and remark and item_remark.strip() == remark.strip():
        item_remark = None  # 두 칸에 같은 글이 오는 일이 많음
    return {
        "written": _ymd(info.get("gdsSpcfcWrtYmd")),
        "base": t("tprtyRnkHypthcStngDts"),
        "keep": t("ndstrcRghCtt"),
        "superficies": t("sprfcExstcDts"),
        "remark": remark,
        "item_remark": item_remark,
    }


def spec_text(spec: dict[str, Any] | None) -> str:
    """명세서에서 사정이 적히는 칸들을 한 글로 (감정가 차이 이유 찾기용)."""
    if not spec:
        return ""
    return " ".join(
        x
        for x in (
            spec.get("keep"),
            spec.get("superficies"),
            spec.get("remark"),
            spec.get("item_remark"),
        )
        if x
    )


def item_spec(c: Any, case_id: str, item_no: int) -> tuple[dict[str, Any] | None, Any]:
    """물건 하나의 명세서와 받은 시각."""
    row = c.execute(
        "select payload, fetched_at from raw.court_doc_raw where case_id = %s and doc_kind = %s order by fetched_at desc limit 1",
        (case_id, f"item_detail_{item_no}"),
    ).fetchone()
    return (spec_sheet(row["payload"]), row["fetched_at"]) if row else (None, None)


def _ts(v: Any) -> str | None:
    return v.strftime("%Y-%m-%d %H:%M") if isinstance(v, datetime) else None


def item_docs(item_id: str) -> dict[str, Any] | None:
    """물건의 사건 원문(가장 최근에 받은 것)."""
    with connect() as c:
        it = c.execute(
            "select case_id, item_no from core.items where item_id = %s", (item_id,)
        ).fetchone()
        if not it:
            return None
        rows = c.execute(
            """select distinct on (doc_kind) doc_kind, payload, fetched_at from raw.court_doc_raw
               where case_id = %s and doc_kind in ('status_report','deliveries')
               order by doc_kind, fetched_at desc""",
            (it["case_id"],),
        ).fetchall()
        spec, spec_at = item_spec(c, it["case_id"], it["item_no"] or 1)
    out: dict[str, Any] = {"status_report": None, "deliveries": None,
                           "spec_sheet": {**spec, "fetched_at": _ts(spec_at)} if spec else None}  # fmt: skip
    for r in rows:
        f = status_report if r["doc_kind"] == "status_report" else deliveries
        out[r["doc_kind"]] = {**f(r["payload"]), "fetched_at": _ts(r["fetched_at"])}
    return out
