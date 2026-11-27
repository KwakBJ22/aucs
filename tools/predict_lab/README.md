# 낙찰가 예측 실험실: 학습 표 + 되짚어 채점

지난 낙찰로 「학습 표」를 만들고, 예측 방식 다섯(① 지금 규칙 · ② 시세 기준 · ③ 머신러닝 · ④ 새 방식 · ⑤ 사다리)을 같은 물건으로 되짚어 채점해 비교 보고서를 낸다.
관리자 · 손님 화면, 분석 엔진(`ENGINE_VERSION`), 서버 DB 는 건드리지 않는다. 이 폴더는 손님 경로(apps/api · workers)에서 읽지 않는다(`tests/test_guards.py`).

## 지킬 것
- 법원경매정보 등 바깥 사이트에 접속하지 않는다.
- Supabase 는 읽기만(select). `export_ours.py` 는 read-only 트랜잭션으로만 연다.
- 강사 자료는 학습 · 검증에만 쓴다.
- 자료 · 결과 파일은 `D:\Auction\data\predict_lab\` 에 둔다(저장소 밖). 저장소에는 코드와 시험만.
- 미래 섞임 금지: 물건마다 매각일 전 자료만, 달마다 그 달 전까지 자료로 배운다.

## 실행 순서 (저장소 맨 위 `D:\Auction\auction-platform` 에서)

1. 강사 zip 의 sqlite 를 실험실 원천 폴더에 한 번 푼다(원본 zip 은 그대로): `uv run --no-project python tools/predict_lab/unpack_instructor.py D:\Auction\_원본\attachments\초기자료_법원매각결과_20261127.zip`
2. 우리 낙찰 자료를 읽기 전용으로 내려받는다(낙찰 + 입찰 전 분석 스냅샷의 낙찰가율 · core.items 주소 · 법원 저감률): `uv run --no-project --with "psycopg[binary]" --with pandas --with pyarrow --with-editable packages/rules python tools/predict_lab/export_ours.py`
3. 학습 표를 만든다(`table_YYYYMMDD.parquet` + 요약 json). 좌표로 지번 찾기(c)에서 브이월드를 부른다 — 하루 한도 `VWORLD_DAILY_LIMIT`(기본 3만) · 결과는 `geo_cache.json` 에 남겨 다시 안 묻는다(한도에 닿으면 다음 날 이어서). 안 부르려면 `--no-geocode`: `uv run --no-project --with pandas --with pyarrow --with pyproj --with httpx --with-editable packages/rules python tools/predict_lab/build_table.py`
4. 되짚어 채점 보고서를 만든다(`report_YYYYMMDD.md` + `.json`): `uv run --no-project --with lightgbm --with scikit-learn --with pandas --with pyarrow --with-editable packages/rules python tools/predict_lab/backtest.py`
5. 시험: `uv run --no-project --with pytest --with lightgbm --with scikit-learn --with pandas --with pyarrow --with pyproj --with httpx --with-editable packages/rules python -m pytest tools/predict_lab/tests -q -p no:cacheprovider`

자료 폴더를 바꾸려면 환경 변수 `PREDICT_LAB_DIR`(결과 폴더)·`REALTRADE_DIR`(실거래 폴더)을 쓴다.

## 파일
- `paths.py` — 자료 · 결과 폴더 위치(`geo_cache.json` 포함).
- `unpack_instructor.py` — 강사 zip 의 sqlite 를 원천 폴더로 푼다.
- `export_ours.py` — 우리 낙찰(`core.sale_results`) + 입찰 전 분석 스냅샷(`analysis.sale_snapshots`: 낙찰가율 p25·p50·p75 · 엔진 버전) + 물건 주소(`core.items`) + 법원 저감률(`ref.rule_tables`)을 읽기 전용으로 내려받는다.
- `usage.py` — 법원 용도 이름 → 종류(아파트 · 빌라 · 오피스텔 · 상가 · 땅 · 그 밖 · 제외). 「기타」는 소분류 코드의 다수결.
- `geo.py` — 좌표(KATEC) → 지번 브이월드 역지오코딩 + 캐시 · 하루 한도.
- `market.py` — 당시 시세. 지번 찾는 순서 (a) 강사 maejibun(등기 설명이라 거의 없음) → (b) core.items 주소 → (c) 좌표 역지오코딩 → (d) 단지 이름(`market_how='name'`). 시세 계산은 `aucs_rules.price.market_price` 를 그대로 부른다. 입찰일 전 거래만.
- `table.py` — 학습 표 순수 함수: 강사 자료 묶기 · 우리 자료 우선 · 거르기 · 유찰 횟수 정하기(`pick_rounds`).
- `build_table.py` — 학습 표 만들기(+ 요약: 시세 붙은 수 (a)~(d) · 유찰 횟수 점검).
- `methods.py` — ① 지금 규칙(운영과 같은 `rate_range` → `court_cell` → `adjusted_rates`) · ② 시세 기준 · 확률 보조 · 달 나누기 · 범위 폭 배수 k.
- `ladder.py` — 강사님 장부(설계서 법원판 낙찰예측장부 5-2 · 5-3)의 방식: 회차 거꾸로 셈 · ④ 새 방식(용도군 × 저감률 × 회차 칸, 법원 칸 우선) · ⑤ 사다리(구 → 법원 → 용도군 → 전 용도).
- `ml.py` — ③ LightGBM 분위수(10·25·50·75·90%) + 팔릴 확률 분류.
- `backtest.py` — 맞춰 보기 · 달마다 「그 달 전까지 배우고 그 달을 맞힘」 · 범위 폭 맞추기 · 보고서 작성.
- `tests/` — 미래 섞임 · ② 30건 미만 제외 · adjusted_rates 상한 · 유찰 횟수 정하기 · 지번 찾는 순서 · 역지오코딩 캐시 · k 가 미래 달을 안 봄 · 손님 경로 격리.

## ① 을 운영과 같게 한 것
- 비교 사례: 운영 `analyze.load_sales` 와 같게 — 낙찰 · 낙찰가율 있음 · 지분 · 특수 · 입찰가 오기(낙찰가율 300%↑ · 최저가 10배↑) 뺌 · 용도는 법원 용도 이름 그대로(`usage_raw`) · 시도는 시도 코드 · 시군구는 「시」 단위 글(운영 `sigungu_from_address` 와 같음: 수원시 권선구 → 수원시) · 면적은 낙찰 표의 칸이 비면 core.items 에서.
- 유찰 횟수: 우리 자료는 `price_round`(운영과 같음). 강사 자료는 최저가로 센 값(DB 의 `core.price_round` 와 같은 셈: ln(최저가÷감정가) ÷ ln(1−법원 저감률)이 정수일 때), 못 세는 물건에는 (법원 `yuchalCnt` · 그 값−1 · 같은 물건의 앞 매각기일 줄 수) 중 센 물건에서 가장 잘 맞은 것(이번에 yuchalCnt−1 이 89%, 앞 기일 수 60%, yuchalCnt 그대로 1.5%).
- 범위: `rate_range` → `court_cell`(관할 법원 차이) → `adjusted_rates`(법원 차이만큼 옮김 · 최저가 아래로 안 감 · 지난 유찰가 위로 안 감). 지난 유찰가에 쓰는 법원 저감률은 운영 `reduction_table` 과 같은 출처(verified 법원, 없으면 30%).
- 맞춰 보기: 입찰 전 분석 스냅샷(`analysis.sale_snapshots`)의 낙찰가율 p25 · p50 · p75 와 견준다. 스냅샷은 만든 날의 엔진 규칙대로라 **rules-0.20.0(price_round) 이상 엔진으로 만든 스냅샷만** 지금 코드와 견줄 수 있다.

## ④ 새 방식 · ⑤ 사다리 (강사님 장부 방식)
- **회차**: 법원 유찰 횟수 칸은 안 믿고, 기준표 court_reduction_pct 의 저감률(20% · 30%)로 사다리 100·(1−저감률)^회차 를 만들어 최저가율에 가장 가까운 회차(0~8)를 고른다. 2%p 넘게 어긋나면 「못 셈」 → ④⑤ 에서 뺀다(①②③ 은 그대로).
- **④** 칸 = 용도군(실험실 종류 6개 — 설계서는 「7개」라고만 해서 Claude 판단) × 저감률 × 회차. 같은 관할 법원 표본이 N건 이상이면 법원 칸, 아니면 법원 없이 그 칸(그것도 5건 미만이면 표본 부족으로 뺌).
- **⑤** 구(시군구) → 관할 법원 → 용도군 전체 → 전 용도 순서로, 같은 저감률 · 회차 안에서 표본이 N건 찰 때까지. 끝까지 안 차도 가장 넓은 단이 5건 이상이면 그것(scope 에 「N 미달」 표시). 어느 단을 썼는지 줄마다 남는다.
- 비교 사례는 입찰일 앞선 365일 안 낙찰만(당일 · 뒤 안 넣음). 금액 = 감정가 × 낙찰가율의 P10·P25·P50·P75·P90, 최저가 밑으로 안 감.
- N(10 · 30 · 50) × 이상치(가: 거르기만 / 나: 비교 사례 낙찰가율에서 사분위 범위 1.5배 밖 뺌) 6조합을 모두 돌리고, 본문에는 ④⑤ 평균 오차가 가장 작은 조합 하나, 부록에 6조합 표.
- 새 잣대(모든 방식): 낙찰가율 기준 |실제율 − P50율| 의 평균(%p) · 가운데 값(%p) · 10%p 넘게 틀린 비율 — 강사님 장부와 같은 잣대. 「이긴 방식」은 이 평균 오차(%p)가 가장 작은 방식, 가운데 오차(%) 기준 승자는 따로 표시.
- 「결과 없음(변경 · 취하)」: 강사님 장부는 채점에서 빼는데 우리 표도 같다(변경 · 취하는 법원 결과에 거의 안 나옴, 불분명 상태는 표를 만들 때 뺌). 가격 채점은 낙찰 건만.
- 설계서 5-6 의 장부 숫자(5.6 / 5.4%p · 11.5 / 12.9%)는 설계서가 「예시」라고 적은 값이라 보고서 (다)에서 나란히만 놓고 까닭은 짐작으로 적는다.

## 결과 읽는 법
- `report_YYYYMMDD.md` 맨 위: (가) 회차 셈 결과(못 셈 건수 · price_round 와 같은 비율) (나) 종류마다 ①~⑤ 같은 물건끼리 평균 오차(%p) · 10%p 넘게 틀린 % · 가운데 오차(%) · 범위 안(원래 / 맞춘 뒤) · 이긴 방식, 시세 「전체(d 포함)」와 「지번만(a·b·c)」 두 가지 (다) 강사님 장부 숫자와 ④⑤ 나란히. 그 아래 ① 맞춰 보기(p50 차이 1%p 안 비율, 90% 넘어야 ②③ 결론) · 부록 6조합 표.
- 가운데 오차 % = 평균( |실제 낙찰가 − 예측 가운데 값| ÷ 실제 낙찰가 ) × 100. 범위 안 % = 실제 낙찰가가 예측 25~75% 구간 안에 든 비율(목표는 50%).
- 범위 폭 맞추기: 방식 · 종류마다 지난달까지 성적으로 배수 k(범위 안 50%가 되게 p50 중심으로 아래 · 위 폭을 k 배)를 정해 그달에 적용. 지난 성적 30건 미만이면 안 맞춤(표 빈칸). 「맞춘 뒤」 숫자는 k 가 있는 달의 물건만이라 같은 건수의 「원래」와 나란히 본다.
- 성적: 건수 · 범위 안(25~75%) % · 낮게 % · 높게 % · 가운데 오차 % · 10%p 넘게 틀린 %. 제외 건수는 방식별 · 종류별.
- 이길 확률 점검(입찰가율 X% 로 쓰면 이길 확률)과 팔릴 확률 점검은 예측 평균과 실제 비율을 10% 칸마다 맞춘 표. 머신러닝이 크게 본 칸 순위도 그대로.
- `table_YYYYMMDD_summary.json`: 원천 행 수 · 겹침 · 거른 건수 · 시세 붙은 건수((a)~(d)별) · 역지오코딩 · 유찰 횟수 점검.

## 알려진 한계
- 강사 자료는 2026-07-28~11-23 17주치뿐이라 배움 자료가 적다(첫 달 배움 1,657건). 8월 성적은 참고만.
- 강사 자료에는 지번 칸이 없다(`maejibun` 은 대부분 등기 설명). 우리 core.items · 좌표 역지오코딩으로 지번을 찾고, 그래도 없을 때만 단지 이름(`buldNm`)으로 맞춘다(그 줄은 `market_how='name'`). 강사 좌표 중 `wgs84*` 칸은 정수 도(127 · 37)뿐이라 못 쓰고 `xCordi · yCordi`(KATEC)를 변환해 쓴다.
- 강사 자료에는 특수 표시가 없어 특수 거르기는 우리 자료에만 걸린다.
- 시군구 이름이 구 없이 쓰인 경우(예: 경기도 화성시)는 법정동 목록으로 고르고, 그래도 못 고르면 빈칸으로 센다.
- 법원 「유찰 횟수」 칸(`yuchalCnt`)은 최저가로 센 값보다 거의 늘 1 크다(이번 점검 35,402건 중 맞은 것 1.5%). 그래서 최저가로 센 값을 쓴다(위 「① 을 운영과 같게 한 것」).
