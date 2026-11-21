-- 0070 core.trade_monthly(실거래 지난 자료 달마다 요약, 412MB) 지우기 — 11/21 대표님 「지워」.
-- 0071 core.trade_yearly(해마다 · 튀는 거래 뺀 중간값)로 바뀌어 코드 어디에서도 안 씀(11/21 grep 확인).
-- 원본은 대표님 PC D:\Auction\data\실거래 에 그대로 — 필요하면 jobs/trade_summary.py 로 다시 만들 수 있음.
drop table if exists core.trade_monthly;
