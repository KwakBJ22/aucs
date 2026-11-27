"""시험 공통: tools/predict_lab 을 import 경로에 넣는다(실행 파일과 같은 방식)."""

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
if str(LAB) not in sys.path:
    sys.path.insert(0, str(LAB))
