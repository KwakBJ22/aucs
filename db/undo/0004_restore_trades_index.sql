-- 0004 되돌리기: 단지명 색인 다시 만들기 (약 77MB). Pro 전환 또는 용량 여유가 생기면 실행.
create index if not exists trades_complex_name_deal_date_idx on core.trades (complex_name, deal_date);
