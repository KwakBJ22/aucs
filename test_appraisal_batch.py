
from pathlib import Path
from datetime import datetime
import csv
import re
import time
import subprocess
import pyautogui

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# ==========================================
# 옥스경매 감정평가서 TXT 일괄 처리 테스트
# ==========================================

BASE_DIR = Path(r"D:\Auction")
SAVE_DIR = BASE_DIR / "감정평가서"
LIST_DIR = SAVE_DIR / "수집목록"
PROFILE_DIR = Path.home() / "ox_selenium_chrome"

COURT_URL = "https://www.courtauction.go.kr/"

LIST_DIR.mkdir(parents=True, exist_ok=True)
SAVE_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


def read_cases():
    today = datetime.now().strftime("%Y%m%d")
    file = LIST_DIR / f"{today}.txt"

    if not file.exists():
        raise FileNotFoundError(
            f"수집목록이 없습니다: {file}"
        )

    cases = []
    seen = set()

    with file.open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        for line_no, row in enumerate(
            csv.reader(f), start=1
        ):
            if not row or not any(row):
                continue

            if len(row) != 3:
                raise ValueError(
                    f"{line_no}행: 항목이 3개가 아닙니다."
                )

            court, case_no, item_no = [
                value.strip() for value in row
            ]

            if not court:
                raise ValueError(
                    f"{line_no}행: 법원명이 없습니다."
                )

            if not re.fullmatch(
                r"\d{4}타경\d+", case_no
            ):
                raise ValueError(
                    f"{line_no}행: 사건번호 오류"
                )

            if not item_no.isdigit():
                raise ValueError(
                    f"{line_no}행: 물건번호 오류"
                )

            key = (court, case_no, item_no)

            if key not in seen:
                seen.add(key)
                cases.append(key)

    return cases


def paste_text(value):
    subprocess.run(
        ["clip"],
        input=value.encode("utf-16le"),
        check=True
    )
    pyautogui.hotkey("ctrl", "v")


def wait_for_pdf(path, timeout=60):
    start = time.monotonic()

    while time.monotonic() - start < timeout:
        if path.exists():
            size1 = path.stat().st_size
            time.sleep(1)
            size2 = path.stat().st_size

            if size1 == size2 and size2 > 1024:
                with path.open("rb") as f:
                    if f.read(5) == b"%PDF-":
                        return True

        time.sleep(0.5)

    return False


def save_pdf(path):
    print("\n5초 후 다운로드 버튼을 클릭합니다.")
    print("PDF 다운로드 버튼 위에")
    print("마우스를 올려놓고 기다리세요.")

    for sec in range(5, 0, -1):
        print(sec)
        time.sleep(1)

    x, y = pyautogui.position()
    pyautogui.click(x, y)

    # Windows '다른 이름으로 저장' 창 대기
    time.sleep(3)

    pyautogui.hotkey("alt", "n")
    time.sleep(0.7)
    pyautogui.hotkey("ctrl", "a")
    paste_text(str(path))
    time.sleep(0.7)
    pyautogui.press("enter")

    return wait_for_pdf(path)


def main():
    cases = read_cases()

    print("=" * 50)
    print("옥스경매 감정평가서 일괄 처리")
    print("=" * 50)
    print("수집 대상:", len(cases), "건")

    options = Options()
    options.add_argument(
        f"--user-data-dir={PROFILE_DIR}"
    )
    options.add_argument("--start-maximized")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(SAVE_DIR),
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": False
        }
    )

    driver = None
    results = []

    try:
        driver = webdriver.Chrome(options=options)
        driver.get(COURT_URL)

        # 동일 사건에 물건이 여러 개라면
        # 물건번호를 파일명에 포함
        counts = {}
        for _, case_no, _ in cases:
            counts[case_no] = counts.get(case_no, 0) + 1

        for index, (court, case_no, item_no) in enumerate(
            cases, start=1
        ):
            if counts[case_no] > 1:
                filename = f"{case_no}_물건{item_no}.pdf"
            else:
                filename = f"{case_no}.pdf"

            target = SAVE_DIR / filename

            print("\n" + "=" * 50)
            print(f"[{index}/{len(cases)}]")
            print("법원:", court)
            print("사건번호:", case_no)
            print("물건번호:", item_no)
            print("저장 파일:", filename)

            if target.exists():
                print("이미 존재: 건너뜁니다.")
                results.append(
                    (court, case_no, item_no, "기존파일")
                )
                continue

            print("\n크롬에서 해당 사건을 검색하세요.")
            print("감정평가서를 열어주세요.")
            print("PDF 내용이 보이면 Enter를 누르세요.")
            print("건너뛰려면 s를 입력하세요.")

            answer = input("진행 (Enter/s): ").strip().lower()

            if answer == "s":
                results.append(
                    (court, case_no, item_no, "건너뜀")
                )
                continue

            success = save_pdf(target)

            if success:
                print("[성공]", target)
                status = "성공"
            else:
                print("[실패] 저장 파일 확인 필요")
                print("저장 창이 남아 있으면 직접 닫으세요.")
                status = "실패"

            results.append(
                (court, case_no, item_no, status)
            )

            if status == "실패":
                answer = input(
                    "다음 사건으로 진행할까요? (y/N): "
                ).strip().lower()
                if answer != "y":
                    break

        log_path = (
            LIST_DIR /
            f"{datetime.now():%Y%m%d}_결과.csv"
        )

        with log_path.open(
            "w", encoding="utf-8-sig", newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerow(
                ["법원명", "사건번호", "물건번호", "결과"]
            )
            writer.writerows(results)

        print("\n========== 처리 결과 ==========")
        for row in results:
            print(*row, sep=" | ")

        print("결과 파일:", log_path)
        print("PDF 저장 폴더:", SAVE_DIR)

    finally:
        input("\nEnter를 누르면 종료합니다...")
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
