"""경매 아카데미(11/14 대표님): 열려 있는 단계 — 화면(apps/web/lib/academy.ko.ts)의 단계 열쇠와 같아야 함.

수업 글은 화면 쪽에 있고, 서버는 「이 단계를 마쳤다」는 요청이 열린 단계인지만 봄(단계마다 포인트 한 번).
"""

# 11/17 레벨 1~7 로 다시 묶음(화면 LEVELS) — 단계 열쇠는 그대로, 「처음에는 피할 물건」만 m1 에서 m0 으로 나옴.
# a 로 시작하는 단계(대항력·배당 · 세금 · 특수물건)는 11/18 법조문 · 판례로 대조해 고친 뒤 엶(대표님 「끝까지 진행해」).
OPEN_STAGES = (
    "s0", "s1", "s2",
    "m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7",
    "a1", "a2", "a3", "a4", "a5", "a6", "a7",
)  # fmt: skip


def ledger_key(stage: str) -> str | None:
    """포인트 내역에 적는 단계 열쇠(「academy:s0」). 열리지 않은 단계면 None."""
    return f"academy:{stage}" if stage in OPEN_STAGES else None


def table_key(stage: str) -> str:
    """기준표 points 에서 읽을 점수 이름 — 중급은 academy_stage_mid, 없으면 academy_stage."""
    return "academy_stage_mid" if stage.startswith("m") else "academy_stage"
