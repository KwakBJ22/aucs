"""아침 분석 뒤 첫 화면 지역 숫자 새로 받아 두기(11/4).

/regions 는 Vercel 앞단이 보관했다 바로 주고(지난 값), 새 값은 뒤에서 받음(stale-while-revalidate).
분석이 끝난 직후 한 번 불러 새로 받게 하고, 잠깐 뒤 한 번 더 불러 새 값이 앞단에 들어갔는지 봄.
그래서 그날 첫 손님도 기다리지 않고 오늘 숫자를 봄. 실패해도 아침 묶음을 멈추지 않음(손님 화면은 지난 값으로 뜸).

    uv run python -m aucs_workers.jobs.warm
"""

import os
import time
import urllib.request

from aucs_workers import db  # noqa: F401  — .env 읽기(AUCS_PUBLIC_API 로 주소를 바꿀 수 있음)

PATHS = ["/regions"]


def main() -> None:
    base = os.environ.get("AUCS_PUBLIC_API", "https://api.aucs.co.kr").rstrip("/")
    for path in PATHS:
        for i in range(2):
            try:
                with urllib.request.urlopen(base + path, timeout=30) as r:
                    print(f"{path} {r.status} {r.headers.get('x-vercel-cache', '')}", flush=True)
            except OSError as e:
                print(f"{path} 못 부름: {e.__class__.__name__}", flush=True)
            if i == 0:
                time.sleep(15)


if __name__ == "__main__":
    main()
