-- 0034 (11/4): 임대 목적 추천(같은 단지 1년 월세 가운데값)·물건 상세 「세놓으면」이 지번으로 전월세를 빨리 찾게
-- (수원·용인·강남 1,000건 기준 4.8초 → 0.16초). Supabase MCP 로 적용함.
create index if not exists trades_lease_lot_idx on core.trades (region_code, lot_no, deal_date)
  where deal_kind = 'lease';
