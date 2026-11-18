
from pathlib import Path
from playwright.sync_api import sync_playwright

# 옥스경매 테스트용 크롬 프로필
PROFILE_DIR = Path.home() / "ox_auction_chrome"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

COURT_URL = "https://www.courtauction.go.kr/"

def main():
    with sync_playwright() as p:

        # 실제 Google Chrome 실행
        # 별도 프로필을 사용해 브라우저 설정 유지
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            channel="chrome",
            headless=False,
            accept_downloads=True,
            viewport={"width": 1440, "height": 900},
            timeout=60000
        )

        # 크롬 창 가져오기
        page = (
            context.pages[0]
            if context.pages
            else context.new_page()
        )

        # 법원경매정보 접속
        page.goto(
            COURT_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        print("=" * 50)
        print("옥스경매 감정평가서 테스트")
        print("=" * 50)

        print("\n테스트 사건")
        print("법원: 서울중앙지방법원")
        print("사건번호: 2024타경116790")
        print("물건번호: 1")

        print("\n[진행 방법]")
        print("1. 크롬에서 사건번호를 검색합니다.")
        print("2. 해당 물건의 상세정보로 이동합니다.")
        print("3. 감정평가서를 클릭합니다.")
        print("4. 로봇 확인이 나오면 직접 처리합니다.")
        print("5. PDF 24페이지가 표시되는지 확인합니다.")

        input(
            "\n감정평가서를 확인한 다음 "
            "여기서 Enter를 누르세요..."
        )

        print("\n========== 최종 진단 ==========")

        for i, current_page in enumerate(context.pages):
            print(f"\n[창 {i + 1}]")
            print("주소:", current_page.url)

            for frame in current_page.frames:
                print("프레임:", frame.url)

        print("\n크롬 프로필 저장 위치:")
        print(PROFILE_DIR)

        print("\n테스트 종료")
        context.close()


if __name__ == "__main__":
    main()
