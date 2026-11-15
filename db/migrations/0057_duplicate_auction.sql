-- 0057 (11/15): 이미 받아 둔 문건 내역에서 「중복경매」를 가려 둠 — 새 수집분은 extract/doc_events 가 가름.
-- 지우는 것 없음. 문건 글에 「중복경매」가 있는 줄의 분류만 바꿈(예: 「채무자겸소유자 ○○ 중복경매통지서 발송」).
update core.case_events set category = '중복경매'
where category <> '중복경매' and (text_masked like '%중복경매%' or text_masked like '%이중경매%');
