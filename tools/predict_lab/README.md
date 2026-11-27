# 낙찰가 예측 실험실: 학습 표 + 되짚어 채점

지난 낙찰로 「학습 표」를 만들고, 예측 방식 셋(① 지금 규칙 · ② 시세 기준 · ③ 머신러닝)을 같은 물건으로 되짚어 채점해 비교 보고서를 낸다.
관리자 · 손님 화면, 분석 엔진(`ENGINE_VERSION`), 서버 DB 는 건드리지 않는다. 이 폴더는 손님 경로(apps/api · workers)에서 읽지 않는다(`tests/test_guards.py`).

## 지킬 것
- 법원경매정보 등 바깥 사이트에 접속하지 않는다.
- Supabase 는 읽기만(select). `export_ours.py` 는 read-only 트랜잭션으로만 연다.
- 강사 자료는 학습 · 검증에만 쓴다.
- 자료 · 결과 파일은 `D:\Auction\data\predict_lab\` 에 둔다(저장소 밖). 저장소에는 코드와 시험만.
- 미래 섞임 금지: 물건마다 매각일 전 자료만, 달마다 그 달 전까지 자료로 배운다.

## 실행 순서 (저장소 맨 위 `D:\Auction\auction-platform` 에서)

1. 강사 zip 의 sqlite 를 실험실 원천 폴더에 한 번 푼다(원본 zip 은 그대로): `uv run --no-project python tools/predict_lab/unpack_instructor.py D:\Auction\_원본\attachments\초기자료_법원매각결과_20261127.zip`
2. 우리 낙찰 자료를 읽기 전용으로 내려받는다: `uv run --no-project --with "psycopg[binary]" --with pandas --with pyarrow --with-editable packages/rules python tools/predict_lab/export_ours.py`
3. 학습 표를 만든다(`table_YYYYMMDD.parquet` + 요약 json): `uv run --no-project --with pandas --with pyarrow --with-editable packages/rules python tools/predict_lab/build_table.py`
4. 되짚어 채점 보고서를 만든다(`report_YYYYMMDD.md` + `.json`): `uv run --no-project --with lightgbm --with scikit-learn --with pandas --with pyarrow --with-editable packages/rules python tools/predict_lab/backtest.py`
5. 시험: `uv run --no-project --with pytest --with lightgbm --with scikit-learn --with pandas --with pyarrow --with-editable packages/rules python -m pytest tools/predict_lab/tests -q -p no:cacheprovider`

자료 폴더를 바꾸려면 환경 변수 `PREDICT_LAB_DIR`(결과 폴더)·`REALTRADE_DIR`(실거래 폴더)을 쓴다.

## 파일
- `paths.py` — 자료 · 결과 폴더 위치.
- `unpack_instructor.py` — 강사 zip 의 sqlite 를 원천 폴더로 푼다.
- `export_ours.py` — 우리 낙찰(`core.sale_results`) + 입찰 전 분석 스냅샷(`analysis.sale_snapshots`)을 읽기 전용으로 내려받는다.
- `usage.py` — 법원 용도 이름 → 종류(아파트 · 빌라 · 오피스텔 · 상가 · 땅 · 그 밖 · 제외). 「기타」는 소분류 코드의 다수결.
- `market.py` — 당시 시세. 실거래를 입찰일 전 자료만으로 붙인다. 계산은 `aucs_rules.price.market_price` 를 그대로 부른다.
- `table.py` — 학습 표 순수 함수: 강사 자료 묶기 · 우리 자료 우선 · 거르기(지분 · 특수 · 동산 · 입찰가 오기).
- `build_table.py` — 학습 표 만들기.
- `methods.py` — ① 지금 규칙(`aucs_rules.sale_rate.rate_range`) · ② 시세 기준 · 확률 보조 · 달 나누기.
- `ml.py` — ③ LightGBM 분위수(10·25·50·75·90%) + 팔릴 확률 분류.
- `backtest.py` — 달마다 「그 달 전까지 배우고 그 달을 맞힘」. 첫 달은 배움용으로만 쓴다. 보고서 작성.
- `tests/` — 미래 섞임 · ② 30건 미만 제외 · 최저가 밑으로 안 감 · 거르기 · 손님 경로 격리.

## 결과 읽는 법
- `report_YYYYMMDD.md` 맨 위: 종류마다 이긴 방식과 세 방식 다 낸 건수, 그리고 방식별 가운데 오차 · 범위 안 %. 이기기는 「세 방식 다 낸 물건」에서 가운데 오차가 가장 작은 방식.
- 가운데 오차 % = 평균( |실제 낙찰가 − 예측 가운데 값| ÷ 실제 낙찰가 ) × 100. 범위 안 % = 실제 낙찰가가 예측 25~75% 구간 안에 든 비율(목표는 50%).
- 성적: 건수 · 범위 안(25~75%) % · 낮게 % · 높게 % · 가운데 오차 % · 10%p 넘게 틀린 %. 제외 건수는 방식별 · 종류별.
- 이길 확률 점검(입찰가율 X% 로 쓰면 이길 확률)과 팔릴 확률 점검은 예측 평균과 실제 비율을 10% 칸마다 맞춘 표.
- `table_YYYYMMDD_summary.json`: 원천 행 수 · 겹침 · 거른 건수 · 시세 붙은 건수.

## 알려진 한계
- 강사 자료는 2026-07-28~11-23 17주치뿐이라 배움 자료가 적다(첫 달 배움 1,657건). 8월 성적은 참고만.
- 강사 자료에는 지번이 없다(`maejibun` 은 등기 설명). 시세는 단지 이름(`buldNm`)으로 맞춘다. 이름이 없거나 실거래 이름과 다르면 시세가 빈다.
- 강사 자료에는 특수 표시가 없어 특수 거르기는 우리 자료에만 걸린다.
- 시군구 이름이 구 없이 쓰인 경우(예: 경기도 화성시)는 법정동 목록으로 고르고, 그래도 못 고르면 빈칸으로 센다.
- 법원 「유찰 횟수」 칸은 믿지 않는 기록이 대표 쪽에 있다(설계서 5-2). 이 표는 법원 칸을 그대로 쓴다.
