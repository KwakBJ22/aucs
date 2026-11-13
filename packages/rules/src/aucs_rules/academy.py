"""경매 아카데미(11/14 대표님): 열려 있는 단계 — 화면(apps/web/lib/academy.ko.ts)의 단계 열쇠와 같아야 함.

수업 글은 화면 쪽에 있고, 서버는 「이 단계를 마쳤다」는 요청이 열린 단계인지만 봄(단계마다 포인트 한 번).
"""

OPEN_STAGES = ("s0", "s1", "s2")  # 초급: 겁 풀기 · 한 바퀴 돌아보기 · 용어 교실 — 중급(m1…) · 고급(a1…)은 교안이 되면 엶


def ledger_key(stage: str) -> str | None:
    """포인트 내역에 적는 단계 열쇠(「academy:s0」). 열리지 않은 단계면 None."""
    return f"academy:{stage}" if stage in OPEN_STAGES else None
