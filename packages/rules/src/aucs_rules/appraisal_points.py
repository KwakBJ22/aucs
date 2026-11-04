"""감정평가 요항(물건상세 aeeWevlMnpntLst) → 화면 요점 · 위험 사실 (11/4 대표님 — 개인정보 가리고 사용 허락).

법원 물건상세에 실린 「감정평가요항표」 요약 글을 읽어
1) 화면에 보일 요점(이름 붙인 짧은 글, 사람 이름·전화는 가림)과
2) 위험 신호 · 추천 점수가 읽는 사실(맹지 · 좁은 길 · 개발제한구역 · 교육환경보호구역 · 토지거래허가구역 · 과밀억제권역 · 역 가까움 …)
을 만든다. 순수 함수 — DB·네트워크를 쓰지 않음.
"""

import html
import re
from typing import Any

from aucs_rules.result import RuleResult, Status

RULE_ID = "APPRAISAL-01"

# 요항 코드 → 이름(화면 순서대로). 같은 이름 코드는 한 칸으로 합침.
LABELS: dict[str, str] = {
    "00083001": "위치·주변",
    "00083003": "교통",
    "00083004": "길",
    "00083005": "길",
    "00083006": "쓰는 모습",
    "00083008": "땅 모양",
    "00083009": "땅 모양",
    "00083011": "토지 이용 계획",
    "00083015": "건물 구조",
    "00083017": "설비",
    "00083013": "제시외 건물",
    "00083018": "제시외 건물",
    "00083014": "서류와 다른 점",
    "00083026": "임대관계·그 밖",
}
ORDER = list(dict.fromkeys(LABELS.values()))
MAX_CHARS = 600  # 임대관계 칸은 임차인 열 명분이 들어오기도 함 — 화면에는 앞부분만

_EMPTY = re.compile(r"^[\s\-.·:()]*((해당\s*사항\s*)?없\s*음|해당\s*없음|무)?[\s\-.·:()]*$")
_ATTACH_ONLY = re.compile(r"^\s*(별첨|후면|첨부)[^.]*참조\.?\s*$")
# 사람 이름 가리기: 「소유자 홍길동」「임차인: 김철수씨」 → 「소유자 홍○○」
_PERSON = re.compile(
    r"(소유자|임차권자|임차인|전세권자|임대인|채무자|채권자|점유자|세입자|거주자|관리인|감정인|입회인|이해관계인)(\s*[:：]?\s*)([가-힣]{2,4}?)(씨|님)?(?=[\s,.)(]|$)"
)
# 「이용욱  840312-*******」처럼 이름 + 주민번호 앞자리(요항 임대관계 칸에 실제로 있음)
_NAME_ID = re.compile(r"([가-힣])([가-힣]{1,3})(\s*)\d{6}\s*-\s*[\d*]{1,7}")
_ID = re.compile(r"\b\d{6}\s*-\s*[\d*]{1,7}")
_PHONE = re.compile(r"\b0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}\b")
_NOT_NAME = {"없음", "미상", "불명", "본인", "가족", "부부", "일가", "등의", "외", "측의"}


def mask_people(text: str) -> str:
    """사람 이름 · 전화번호를 가림(11/4 — 사용 허락 조건: 개인정보 마킹)."""

    def _name(m: re.Match[str]) -> str:
        name = m.group(3)
        if name in _NOT_NAME or name.endswith(("으로", "에게", "이며", "이고", "과", "와")):
            return m.group(0)
        return f"{m.group(1)}{m.group(2)}{name[0]}{'○' * (len(name) - 1)}"

    t = _NAME_ID.sub(lambda m: f"{m.group(1)}{'○' * len(m.group(2))}", text)
    t = _ID.sub("", t)
    return _PHONE.sub("○○○-○○○○-○○○○", _PERSON.sub(_name, t))


def clean(text: str | None) -> str:
    """법원 글의 &amp;quot; 같은 겹친 기호 · <br> · 줄바꿈을 풀어 한 줄로."""
    t = str(text or "")
    for _ in range(3):  # &amp;apos; 처럼 두 번 감싼 것까지
        u = html.unescape(t)
        if u == t:
            break
        t = u
    t = re.sub(r"<br\s*/?>", " ", t, flags=re.I)
    t = re.sub(r"\s*\n\s*", " ", t.replace("\r", ""))
    return re.sub(r"\s{2,}", " ", t).strip().strip('"').strip()


def parse_points(lst: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """요항 목록 → [{label, text}] (빈 칸 · 「없음」 · 「별첨 참조」만인 칸은 뺌, 이름 가림)."""
    by_label: dict[str, list[str]] = {}
    for e in sorted(
        lst or [],
        key=lambda x: (str(x.get("aeeWevlMnpntItmCd")), int(x.get("aeeWevlMnpntDtlSeq") or 0)),
    ):
        label = LABELS.get(str(e.get("aeeWevlMnpntItmCd") or ""))
        t = clean(e.get("aeeWevlMnpntCtt"))
        if not label or not t or _EMPTY.match(t) or _ATTACH_ONLY.match(t):
            continue
        t = mask_people(t)
        if t not in by_label.setdefault(label, []):
            by_label[label].append(t)
    out = []
    for k in ORDER:
        if k in by_label:
            t = " ".join(by_label[k])
            out.append(
                {
                    "label": k,
                    "text": t if len(t) <= MAX_CHARS else t[: MAX_CHARS - 1].rstrip() + "…",
                }
            )
    return out  # fmt: skip


_STATION = re.compile(r"['\"‘’“”]?([가-힣A-Za-z0-9]{1,12}역)(?![가-힣])")
_NOT_STATION = (
    "지역",
    "구역",
    "권역",
    "영역",
    "전역",
    "일역",
    "역세",
    "광역",
    "시역",
    "해역",
    "유역",
    "경역",
)
_ROAD_W = re.compile(r"(\d+(?:\.\d+)?)\s*(?:[~\-]\s*(\d+(?:\.\d+)?))?\s*(?:m|M|미터|ｍ)")


def _station(t: str) -> str | None:
    """역 이름 하나(「사우역」). 「지역·구역」 같은 말은 뺌."""
    for m in _STATION.finditer(t):
        name = m.group(1)
        if name.endswith(("지하철역", "전철역", "기차역")):
            continue
        if (
            len(name) >= 2
            and not name.endswith(_NOT_STATION)
            and not any(w in name for w in _NOT_STATION)
        ):
            return name
    return None


def _max_road_m(t: str) -> float | None:
    """길 글에서 가장 넓은 길 폭(m). 「노폭 약 2~3m」 → 3."""
    ws = [float(b or a) for a, b in _ROAD_W.findall(t)]
    ws = [w for w in ws if 0 < w < 100]
    return max(ws) if ws else None


def appraisal_facts(points: list[dict[str, str]]) -> RuleResult:
    """요점 글 → 위험 신호 · 추천이 읽는 사실 묶음. 글이 없으면 빈 묶음(「모름」 — 없다고 보지 않음)."""
    p = {x["label"]: x["text"] for x in points}
    plan, road = p.get("토지 이용 계획", ""), p.get("길", "")
    near, other = f"{p.get('위치·주변', '')} {p.get('교통', '')}", p.get("임대관계·그 밖", "")
    f: dict[str, Any] = {}
    ev: list[dict[str, Any]] = []
    if not points:
        return RuleResult(f, Status.UNKNOWN, RULE_ID, ev)
    if re.search(r"토지\s*거래\s*(계약에\s*관한\s*)?허가\s*구역", plan):
        f["land_permit_area"] = True
        ev.append({"land_permit_area": "토지 이용 계획"})
    if re.search(r"개발\s*제한\s*구역", plan) and not re.search(
        r"개발\s*제한\s*구역\s*(해제|밖)", plan
    ):
        f["greenbelt"] = True
    if re.search(
        r"교육\s*환경\s*보호|상대\s*보호\s*구역|절대\s*보호\s*구역|학교\s*환경\s*위생", plan
    ):
        f["edu_protect"] = True
    if "과밀억제권역" in plan:
        f["overcrowded"] = True
    blind = f"{road} {other}"
    if "맹지" in blind:
        # 「지적도상 맹지이나 현황 도로와 접함」은 확인 필요, 그냥 「맹지임」은 길 없음
        f["no_road"] = (
            "check" if re.search(r"맹지[^.]*(이나|이지만|나)[^.]*(현황|사실상)", blind) else "yes"
        )
    if (w := _max_road_m(road)) is not None:
        f["road_max_m"] = w
        if w < 4:
            f["narrow_road"] = True
    if p.get("제시외 건물"):
        f["extra_building_text"] = True
    if p.get("서류와 다른 점"):
        f["doc_diff_text"] = True
    if re.search(r"임대\s*관계[^.]*(미상|불명|조사하지\s*못|확인\s*불가)|폐문", other):
        f["lease_unknown_appraisal"] = True
    if st := _station(near):
        f["near_station"] = st
    if re.search(r"초등학교", p.get("위치·주변", "")):
        f["near_school"] = True
    return RuleResult(f, Status.ESTIMATED, RULE_ID, ev)
