# 2번 PC 설치(서류 보관 담당) — 11/26

1번 PC 와 **다른 인터넷**에 두고, 같은 DB 를 씀. 하루 법원 한도는 PC 마다 따로(처음 8,000번, 3일 무사하면 20%씩).
맡는 일: 매시 서류 보관(현황조사서 · 문건송달) · 14시 뒤 전국 보관. 2번 PC 가 90분 넘게 꺼져 있으면 1번 PC 가 대신 함.

1. 윈도우 · 크롬 설치, 인터넷 연결(1번 PC 와 다른 회선)
2. Git 설치 → `D:\Auction` 에서 `git clone https://github.com/KwakBJ22/aucs auction-platform`
3. uv 설치: PowerShell `irm https://astral.sh/uv/install.ps1 | iex` → 새 창에서 `cd D:\Auction\auction-platform; uv sync --all-packages; uv run playwright install chrome`(크롬이 있으면 건너뜀)
4. 1번 PC 의 `.env` 를 USB 등으로 복사(인터넷에 올리지 말 것) → 맨 아래에 `AUCS_ROLE=docs` 한 줄
5. PowerShell(관리자)로 `.\scripts\register-tasks-docs.ps1`
6. Claude 데스크톱 앱에서 이 대화에 `D:\Auction` 폴더를 연결 → 코워크가 첫 차례를 확인

코드를 바꾼 뒤에는 2번 PC 에서도 `git pull`(1번 PC 에서 push 한 다음).
