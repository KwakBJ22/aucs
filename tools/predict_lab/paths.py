"""자료 · 결과 폴더 위치. 저장소 밖(D:\\Auction\\data\\predict_lab) — 저장소에는 코드와 시험만 둔다.

바꾸려면 환경 변수 PREDICT_LAB_DIR · REALTRADE_DIR.
"""

import os
from pathlib import Path

LAB_DIR = Path(os.environ.get("PREDICT_LAB_DIR", r"D:\Auction\data\predict_lab"))
SRC_DIR = LAB_DIR / "src"  # 원천 복사본(강사 자료 · 우리 자료 내보내기) — 손님 경로에서 읽지 않음
INSTRUCTOR_DB = SRC_DIR / "강사_법원매각결과.sqlite"
OURS_PARQUET = SRC_DIR / "우리_낙찰.parquet"
REALTRADE_DIR = Path(os.environ.get("REALTRADE_DIR", r"D:\Auction\data\실거래"))
SGG_JSON = REALTRADE_DIR / "sgg.json"
