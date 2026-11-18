
from pathlib import Path
import time
import subprocess
import pyautogui

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# =========================================
# 옥스경매 감정평가서 저장 테스트
# =========================================

COURT_URL = "https://www.courtauction.go.kr/"
CASE_NO = "2024타경116790"

PROFILE_DIR = Path.home() / "ox_selenium_chrome"
SAVE_DIR = Path(r"D:\Auction\감정평가서")

PROFILE_DIR.mkdir(parents=True, exist_ok=True)
SAVE_DIR.mkdir(parents=True, exist_ok=True)

SAVE_FILE = SAVE_DIR / f"{CASE_NO}.pdf"

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


def paste_text(text):
    """한글 경로를 클립보드로 입력"""
    subprocess.run(
        ["clip"],
        input=text.encode("utf-16le"),
        check=True
    )
    pyautogui.hotkey("ctrl", "v")


def wait_for_file(path, timeout=30):
    """저장된 PDF 파일 확인"""
    start = time.monotonic()

    while time.monotonic() - start < timeout:
        if path.exists():
            size1 = path.stat().st_size
            time.sleep(1)
            size2 = path.stat().st_size

            if size1 == size2 and size2 > 1024:
                with open(path, "rb") as f:
                    if f.read(5) == b"%PDF-":
                        return True

        time.sleep(0.5)

    return False


def main():
    driver = None

    if SAVE_FILE.exists():
        print("이미 파일이 존재합니다:")
        print(SAVE_FILE)
        print("기존 파일은 덮어쓰지 않습니다.")
        return

    try:
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

        driver = webdriver.Chrome(options=options)
        driver.get(COURT_URL)

        print("=" * 45)
        print("옥스경매 감정평가서 자동 저장")
        print("=" * 45)
        print("사건번호:", CASE_NO)
        print("저장 위치:", SAVE_FILE)

        print("\n[1단계]")
        print("크롬에서 감정평가서를 열어주세요.")
        print("PDF가 정상 표시되는지 확인하세요.")

        input(
            "\n감정평가서가 보이면 "
            "Enter를 누르세요..."
        )

        print("\n[2단계]")
        print("5초 후 마우스 위치를 클릭합니다.")
        print("다운로드 버튼 위에 마우스를 올려두세요.")

        for sec in range(5, 0, -1):
            print(sec)
            time.sleep(1)

        # PDF 다운로드 버튼 클릭
        x, y = pyautogui.position()
        pyautogui.click(x, y)

        print("\n저장 창이 열릴 때까지 기다립니다.")
        time.sleep(3)

        # Windows 다른 이름으로 저장 창
        # Alt+N: 파일 이름 입력란
        pyautogui.hotkey("alt", "n")
        time.sleep(0.7)

        # 전체 저장 경로 입력
        pyautogui.hotkey("ctrl", "a")
        paste_text(str(SAVE_FILE))
        time.sleep(0.7)

        # 저장 실행
        pyautogui.press("enter")

        print("\n저장 요청 완료")
        print("파일 확인 중...")

        if wait_for_file(SAVE_FILE):
            print("\n[성공] 감정평가서 저장 완료")
            print(SAVE_FILE)
        else:
            print("\n[확인 필요]")
            print("파일이 지정 폴더에서 확인되지 않습니다.")
            print("저장 창이 남아 있는지 확인하세요.")

    except Exception as e:
        print("\n오류 발생:", e)

    finally:
        input("\nEnter를 누르면 종료합니다...")
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
