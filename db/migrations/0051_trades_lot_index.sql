-- 0051 실거래 지번 색인(11/14): 같은 지번의 거래를 찾을 때 동 전체를 훑었음
-- (분석 6만 번 × 0.02초, 물건 상세 0.3초). 지역 · 지번 · 날짜로 바로 찾게. 만드는 데 10~30초.
create index if not exists trades_lot_idx on core.trades (region_code, lot_no, deal_date);
analyze core.trades;
