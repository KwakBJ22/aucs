"""지킴 시험: 강사 자료는 손님 경로에서 읽지 않는다 · 자료 폴더는 저장소 밖 · 바깥 사이트 접속 없음."""

from pathlib import Path

from paths import LAB_DIR

REPO = Path(__file__).resolve().parents[3]
CUSTOMER_PATHS = ["apps/api", "apps/web", "workers", "packages", "db"]
FORBIDDEN = ["predict_lab", "강사_법원매각결과", "tools/predict_lab", "PREDICT_LAB"]


def test_자료_폴더는_저장소_밖():
    assert REPO not in LAB_DIR.resolve().parents
    assert not str(LAB_DIR.resolve()).startswith(str(REPO))


def test_손님_경로에서_실험실을_읽지_않는다():
    hits = []
    for folder in CUSTOMER_PATHS:
        root = REPO / folder
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {
                ".py",
                ".ts",
                ".tsx",
                ".js",
                ".mjs",
                ".sql",
                ".toml",
            }:
                continue
            if "node_modules" in path.parts or "__pycache__" in path.parts or ".venv" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for word in FORBIDDEN:
                if word in text:
                    hits.append(f"{path.relative_to(REPO)}: {word}")
    assert hits == []


def test_실험실_코드에_바깥_사이트_주소가_없다():
    banned = ["courtauction.go.kr", "ggi", "지지옥션", "requests.get", "httpx.get", "urlopen"]
    for path in Path(__file__).resolve().parents[1].glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for word in banned:
            assert word not in text, f"{path.name}: {word}"
