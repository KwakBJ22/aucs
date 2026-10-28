"""온비드 응답 한 줄 → 정리한 값(순수 함수). 칸 이름은 원문 스킬(collectors/onbid SKILL, 9/8 실측) 기준이고,
이름이 달라도 버티게 후보를 여럿 둠. 원본은 raw.onbid_raw 에 그대로 남으니 틀리면 여기만 고쳐 다시 정리하면 됨."""

import re
from datetime import datetime, timedelta, timezone
from typing import Any

KST = timezone(timedelta(hours=9))


def pick(r: dict[str, Any], *names: str) -> Any:
    """후보 칸 이름 중 처음으로 값이 있는 것."""
    for n in names:
        v = r.get(n)
        if v not in (None, "", "-"):
            return v
    return None


def to_int(v: Any) -> int | None:
    if v in (None, ""):
        return None
    try:
        return int(float(str(v).replace(",", "").strip()))
    except ValueError:
        return None


def to_num(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def to_dt(v: Any) -> datetime | None:
    """「202610291700」「20261029」「2026-10-29 17:00」 → KST 시각. 일정 미정(2999·9999년)은 None."""
    if v in (None, ""):
        return None
    s = re.sub(r"[^0-9]", "", str(v))
    if len(s) < 8 or not ("2000" <= s[:4] <= "2100"):
        return None
    s = (s + "0000")[:12]
    try:
        return datetime.strptime(s, "%Y%m%d%H%M").replace(tzinfo=KST)
    except ValueError:
        return None


_FINANCE_ORG = re.compile(r"은행|신용협동조합|신협|새마을금고|저축은행|캐피탈|보험")


def kind_of(name: str | None, code: str | None = None, org: str | None = None) -> str:
    """재산 종류: seized 압류 · trust 신탁 · public 국유·공유·수탁 · finance 금융기관 담보 · general 그 밖.
    신탁사 물건은 온비드가 「기타일반재산」으로 줌(10/28 실측 853건) → 맡긴 곳(orgNm)으로 가려냄."""
    n, o = name or "", org or ""
    if "압류" in n or code == "0007":
        return "seized"
    if "신탁" in n or "신탁" in o:
        return "trust"
    if "기타일반" in n and _FINANCE_ORG.search(o):
        return "finance"
    if any(w in n for w in ("국유", "공유", "수탁")):
        return "public"
    if "금융" in n:
        return "finance"
    return "general"


_LOT = re.compile(r"(?:^|\s)((?:산\s*)?\d{1,5}(?:-\d{1,5})?)(?=\s|$|,|번지|외)")


def lot_from_pnu(pnu: Any) -> str | None:
    """필지 번호(PNU 19자리: 법정동 10 + 산 1 + 본번 4 + 부번 4) → 「470-12」·「산12-3」."""
    p = str(pnu or "")
    if len(p) != 19 or not p.isdigit() or int(p[11:15]) == 0:
        return None
    lot = str(int(p[11:15])) + (f"-{int(p[15:19])}" if int(p[15:19]) else "")
    return f"산{lot}" if p[10] == "2" else lot


def lot_from(text: str | None, dong: str | None) -> str | None:
    """「… 신현리 470-12 107동 …」 → 「470-12」. 동·리 이름 바로 뒤 번지만 믿음."""
    if not text or not dong:
        return None
    i = text.find(dong)
    if i < 0:
        return None
    m = _LOT.match(text[i + len(dong) :])
    return m.group(1).replace(" ", "") if m else None


_DONG = re.compile(r"\s([가-힣][가-힣0-9]*(?:동|가|리|읍|면))(?=\s|$)")


def address_of(r: dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None]:
    """(주소, 시도, 시군구, 읍면동). 구조화 칸(lctn*)을 먼저, 없으면 물건명에서."""
    sido = pick(r, "lctnSdnm", "sido", "ctpvNm")
    sgg = pick(r, "lctnSggnm", "sgg", "sggNm")
    emd = pick(r, "lctnEmdNm", "emd", "emdNm")
    full = pick(r, "ldnmAdrs", "lctnAdrs", "cltrAdrs", "nmrdAdrs", "rdnmAdrs")
    title = str(pick(r, "cltrNm", "onbidCltrNm") or "")
    if not full and sido and title.find(str(sido)) >= 0:
        full = title[title.find(str(sido)) :]
    if not full:
        full = " ".join(str(x) for x in (sido, sgg, emd) if x) or None
    if full and not emd:
        m = _DONG.search(" " + str(full))
        emd = m.group(1) if m else None
    return (str(full).strip() if full else None), sido, sgg, emd


def parse_item(r: dict[str, Any]) -> dict[str, Any] | None:
    """물건 목록(OnbidRlstListSrvc2) 한 줄 = 한 회차. 물건관리번호가 없으면 None."""
    mng = pick(r, "cltrMngNo", "onbidCltrMngNo")
    if not mng:
        return None
    addr, sido, sgg, emd = address_of(r)
    app = to_int(pick(r, "apslEvlAmt", "apslAsesAvgAmt"))
    mn = to_int(pick(r, "lowstBidPrcIndctCont", "minBidPrc", "lowstBidPrc"))
    kind_name = pick(r, "prptDivNm")
    title = pick(r, "cltrNm", "onbidCltrNm")
    return {
        "item_id": f"OB-{mng}",
        "mng_no": str(mng),
        "cond_no": str(pick(r, "pbctCdtnNo", "pbctNo", "pbctNsq") or ""),
        "notice_no": pick(r, "onbidPbancNo", "pbancNo"),
        "kind": kind_of(kind_name, pick(r, "prptDivCd"), pick(r, "orgNm")),
        "kind_name": kind_name,
        "disposal": pick(r, "dspsMthodNm", "dpslMtdNm"),
        "title": title,
        "address": addr,
        "sido": sido,
        "sigungu": sgg,
        "dong": emd,
        "lot_no": lot_from_pnu(pick(r, "ltnoPnu"))
        or lot_from(addr, emd)
        or lot_from(str(title or ""), emd),
        "pnu_region": str(pick(r, "ltnoPnu") or "")[:10] or None,
        "usage_name": pick(r, "ctgrFullNm", "cltrUsgSclsCtgrNm", "cltrUsgMclsCtgrNm", "usgNm"),
        "land_m2": to_num(pick(r, "landSqms", "landArea", "lndSqms")),
        "building_m2": to_num(pick(r, "bldSqms", "bldgArea", "bldSqm")),
        "appraisal_krw": app or None,
        "min_price_krw": mn or None,
        "failed_count": to_int(pick(r, "usbdNft", "usbdCnt")),
        "bid_start": to_dt(pick(r, "cltrBidBgngDt", "pbctBegnDtm", "bidBgngDt")),
        "bid_end": to_dt(pick(r, "cltrBidEndDt", "pbctClsDtm", "bidEndDt")),
        "open_at": to_dt(pick(r, "cltrOpbdDt", "opbdDt", "pbctExctDtm")),
        "status_name": pick(r, "pbctStatNm", "pbctCltrStatNm"),
    }


def parse_notice(r: dict[str, Any]) -> dict[str, Any] | None:
    no = pick(r, "onbidPbancNo", "pbancNo")
    if not no:
        return None
    d = to_dt(pick(r, "pbancYmd", "pbancDt"))
    return {
        "notice_no": str(no),
        "notice_date": d.date() if d else None,
        "name": pick(r, "onbidPbancNm", "pbancNm"),
        "org_name": pick(r, "orgNm", "pbancOrgNm", "exctOrgNm"),
        "kind_name": pick(r, "prptDivNm"),
    }


def rate(a: int | None, b: int | None) -> float | None:
    return round(a * 100 / b, 2) if a and b else None


def parse_result(r: dict[str, Any]) -> dict[str, Any] | None:
    """입찰결과(OnbidCltrBidRsltListSrvc2) 한 줄. 최저가 대비 낙찰가율은 원본 칸이 비면 직접 계산."""
    mng = pick(r, "cltrMngNo", "onbidCltrMngNo")
    opened = to_dt(pick(r, "opbdDt", "cltrOpbdDt", "pbctOpbdDtm"))
    if not mng or not opened:
        return None
    app = to_int(pick(r, "apslEvlAmt"))
    mn = to_int(pick(r, "lowstBidPrcIndctCont", "lowstBidPrc"))
    win = to_int(pick(r, "scsbdAmt", "bidPrc", "sucBidAmt")) or None
    title = pick(r, "cltrNm", "onbidCltrNm")
    return {
        "mng_no": str(mng),
        "opened_at": opened,
        "notice_no": str(pick(r, "onbidPbancNo", "pbancNo") or ""),
        "item_seq": pick(r, "cltrNo", "onbidCltrNo"),
        "kind_name": pick(r, "prptDivNm"),
        "disposal": pick(r, "dspsMthodNm"),
        "usage_l": pick(r, "ctgrLclsNm", "cltrUsgLclsCtgrNm"),
        "usage_m": pick(r, "ctgrMclsNm", "cltrUsgMclsCtgrNm"),
        "usage_s": pick(r, "ctgrSclsNm", "cltrUsgSclsCtgrNm"),
        "title": title,
        "sido": str(title).split()[0] if title else None,
        "land_m2": to_num(pick(r, "landSqms")),
        "building_m2": to_num(pick(r, "bldSqms")),
        "appraisal_krw": app or None,
        "min_price_krw": mn or None,
        "win_krw": win,
        "failed_round": to_num(pick(r, "usbdNft")),
        "bidders": to_int(pick(r, "vldBidrCnt", "bidrCnt")),
        "invalid_bidders": to_int(pick(r, "ivldBidrCnt")),
        "rate_appraisal": to_num(pick(r, "apslEvlAmtCtrsScfbPrcRto")) or rate(win, app),
        "rate_min": to_num(pick(r, "lowstBidCtrsScfbPrcRto")) or rate(win, mn),
        "result": pick(r, "pbctStatNm", "bidRsltNm", "pbctCltrStatNm"),
        "source": "api",
    }


def current_round(rounds: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """물건의 「지금 회차」: 입찰 마감이 아직 안 지난 것 중 가장 이른 것, 없으면 가장 늦은 것."""
    ahead = [x for x in rounds if x["bid_end"] and x["bid_end"] >= now]
    if ahead:
        return min(ahead, key=lambda x: x["bid_end"])
    dated = [x for x in rounds if x["bid_end"]]
    return max(dated, key=lambda x: x["bid_end"]) if dated else rounds[0]
