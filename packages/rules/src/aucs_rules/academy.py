"""경매 아카데미(11/14 대표님): 열려 있는 단계 — 화면(apps/web/lib/academy.ko.ts)의 단계 열쇠와 같아야 함.

수업 글은 화면 쪽에 있고, 서버는 「이 단계를 마쳤다」는 요청이 열린 단계인지만 봄(단계마다 포인트 한 번).
"""

# 초급 s0~s2(겁 풀기 · 한 바퀴 · 용어 교실), 중급 m1~m7(내 첫 입찰 준비 — 수업마다 옥스에서 해 보는 과제).
# 고급(a1…)은 법률 검토 뒤에 엶 — 화면에서 읽을 수는 있고 포인트는 없음.
OPEN_STAGES = ("s0", "s1", "s2", "m1", "m2", "m3", "m4", "m5", "m6", "m7")


def ledger_key(stage: str) -> str | None:
    """포인트 내역에 적는 단계 열쇠(「academy:s0」). 열리지 않은 단계면 None."""
    return f"academy:{stage}" if stage in OPEN_STAGES else None


def table_key(stage: str) -> str:
    """기준표 points 에서 읽을 점수 이름 — 중급은 academy_stage_mid, 없으면 academy_stage."""
    return "academy_stage_mid" if stage.startswith("m") else "academy_stage"
