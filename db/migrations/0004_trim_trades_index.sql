-- 0004 무료 한도(500MB) 여유를 위해 단지명 색인 제거 (10/17 대표님 결정, 임시 조치)
-- 되돌리기: db/undo/0004_restore_trades_index.sql — Pro로 올리거나 용량 여유가 생기면 반드시 다시 만듭니다.
drop index if exists core.trades_complex_name_deal_date_idx;
