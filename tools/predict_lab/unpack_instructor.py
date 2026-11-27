"""강사 자료(zip 안 sqlite)를 실험실 원천 폴더로 한 번 풀어 둔다. 원본 zip 은 그대로 둔다(읽기만).

실행: uv run --no-project python tools/predict_lab/unpack_instructor.py <zip 경로>
"""

import shutil
import sys
import zipfile
from pathlib import Path

from paths import INSTRUCTOR_DB, SRC_DIR


def unpack(zip_path: Path) -> Path:
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        members = [i for i in z.infolist() if i.filename.lower().endswith(".sqlite")]
        if len(members) != 1:
            raise SystemExit(f"zip 안에 sqlite 가 {len(members)}개입니다(1개여야 함)")
        with z.open(members[0]) as src, open(INSTRUCTOR_DB, "wb") as dst:
            shutil.copyfileobj(src, dst)
    return INSTRUCTOR_DB


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("사용법: unpack_instructor.py <zip 경로>")
    print(f"강사 자료 → {unpack(Path(sys.argv[1]))}")
