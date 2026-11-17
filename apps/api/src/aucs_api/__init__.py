"""옥스 API.

11/18: 서버(Vercel)는 세계 표준시(UTC)라 date.today() 가 한국 0~9시에 「어제」였음 — 끝난 물건이 「오늘 입찰(D-0)」로
홈 「나에게 맞는 물건」 맨 앞을 채웠음. 이 패키지를 처음 읽을 때 한국 시각으로 맞춤(파이썬 날짜만 — DB 의 current_date 는 따로).
"""

import os
import time

os.environ["TZ"] = "Asia/Seoul"
if hasattr(time, "tzset"):  # 윈도우(대표님 PC 개발 서버)에는 없음 — 그곳은 원래 한국 시각
    time.tzset()
