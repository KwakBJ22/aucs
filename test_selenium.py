
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

# ========================================
# 옥스경매 감정평가서 Selenium 1건 테스트
# ========================================

COURT_URL = "https://www.courtauction.go.kr/"

CASE_NO = "2024타경116790"
COURT_NAME = "서울중앙지방법원"

# 테스트 전용 크롬 프로필
PROFILE_DIR = Path.home() / "ox_selenium_chrome"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# 다운로드 폴더
DOWNLOAD_DIR = Path.home() / "Downloads" / "옥스경매_감정평가서"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def main():
    options = Options()

    # 일반 Google Chrome 실행
    options.add_argument(
        f"--user-data-dir={PROFILE_DIR}"
    )
    options.add_argument("--start-maximized")

    # PDF가 표시되는지 먼저 확인하기 위해
    # PDF 뷰어를 비활성화하지 않습니다.

    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(DOWNLOAD_DIR),
            "download.prompt_for_download": False,
        }
    )

    driver = None

    try:
        print("=" * 50)
        print("옥스경매 감정평가서 Selenium 테스트")
        print("=" * 50)

        print("\n크롬을 실행합니다...")

        driver = webdriver.Chrome(options=options)

        driver.set_page_load_timeout(60)
        driver.get(COURT_URL)

        print("\n테스트 사건:")
        print("법원:", COURT_NAME)
        print("사건번호:", CASE_NO)
        print("물건번호: 1")

        print("\n[진행 방법]")
        print("1. 열린 크롬에서 사건번호 검색")
        print("2. 해당 물건 상세화면 이동")
        print("3. 감정평가서 클릭")
        print("4. 로봇 확인이 나오면 직접 처리")
        print("5. 감정평가서가 표시되는지 확인")

        print("\n현재는 클릭을 자동화하지 않습니다.")

        input(
            "\n감정평가서 화면을 확인한 뒤 "
            "Enter를 누르세요..."
        )

        print("\n========== 실행 결과 ==========")

        handles = driver.window_handles

        print("열린 창 수:", len(handles))

        for i, handle in enumerate(handles):
            try:
                driver.switch_to.window(handle)

                print(f"\n[창 {i + 1}]")
                print("제목:", driver.title)
                print("URL:", driver.current_url)

                frames = driver.find_elements(
                    "tag name", "iframe"
                )

                print("iframe 수:", len(frames))

                for frame in frames:
                    print(
                        "iframe 주소:",
                        frame.get_attribute("src")
                    )

            except WebDriverException as e:
                print("창 확인 오류:", str(e)[:200])

        print("\n다운로드 폴더:", DOWNLOAD_DIR)
        print("\n진단 완료")

        input("\nEnter를 누르면 크롬이 종료됩니다...")

    except Exception as e:
        print("\n오류 발생:", str(e))
        input("\nEnter를 누르면 종료합니다...")

    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
