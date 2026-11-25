-- 11/25 점검: 법원이 준 빈 답({"ipcheck": …}뿐, 빈 물건상세)을 「가장 최근 서류」로 넣어 두어
--   현황조사 · 문건송달 · 기일 · 사건정보를 읽는 곳이 빈 것을 봤음 → 내용 없는 줄을 지움(예전 내용 있는 줄이 다시 최신이 됨).
--   수집기는 이제 빈 답을 넣지 않음.
delete from raw.court_doc_raw
 where (doc_kind in ('status_report','deliveries','schedule','case_info')
        and not exists (select 1 from jsonb_object_keys(payload) k where k <> 'ipcheck'))
    or (doc_kind like 'item_detail_%' and jsonb_typeof(payload->'dma_result') is distinct from 'object');
