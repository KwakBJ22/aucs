-- 0033 (11/4 대표님): 철원군 물건은 수도권이 아니라 DB에서 지움 · 인천지방법원을 수집 법원에 더함
-- 철원 물건이 다른 지역 물건과 같은 사건에 묶여 있으면 사건은 남기고 철원 물건만 지움.
create temp table cw as
  select item_id, case_id, doc_key from core.items where sigungu = '철원군' or address like '%철원군%';
create temp table cwc as
  select distinct case_id from cw c
  where not exists (select 1 from core.items i where i.case_id = c.case_id and i.item_id not in (select item_id from cw));

delete from analysis.risk_signals where item_id in (select item_id from cw);
delete from analysis.item_analysis where item_id in (select item_id from cw);
delete from analysis.item_data_status where item_id in (select item_id from cw);
delete from analysis.signal_overrides where item_id in (select item_id from cw);
delete from app.alert_events where item_id in (select item_id from cw);
delete from app.compare_exclusions where item_id in (select item_id from cw);
delete from app.value_reports where item_id in (select item_id from cw);
delete from app.uploaded_registries where item_id in (select item_id from cw);
delete from app.bid_results where item_id in (select item_id from cw);
delete from core.item_parts where item_id in (select item_id from cw);
delete from core.rounds where item_id in (select item_id from cw);
delete from core.rights where item_id in (select item_id from cw) or case_id in (select case_id from cwc);
delete from core.tenants where item_id in (select item_id from cw) or case_id in (select case_id from cwc);
delete from core.sale_results where item_id in (select item_id from cw) or address like '%철원군%';
delete from raw.court_item_raw where doc_key in (select doc_key from cw);
delete from raw.court_result_raw where payload::text like '%철원군%';
delete from core.items where item_id in (select item_id from cw);
delete from core.documents where case_id in (select case_id from cwc);
delete from core.case_events where case_id in (select case_id from cwc);
delete from raw.court_doc_raw where case_id in (select case_id from cwc);
delete from core.cases where case_id in (select case_id from cwc);
delete from core.onbid_results where sido like '%철원%';

insert into ref.courts (court_code, name_ko, sido) values ('B000240', '인천', '인천광역시')
on conflict (court_code) do nothing;

-- 옛 시군구 이름 → 지금 이름(수집기 parse.fix_sigungu 와 같은 규칙)
update core.items set sigungu = '평택시' where sido = '경기도' and sigungu = '평택군';
update core.items set sigungu = case
    when address ~ '(운서|운남|운북|중산|을왕|남북|덕교|무의)동' then '영종구' else '제물포구' end
  where sido = '인천광역시' and sigungu = '중구';
update core.items set sigungu = '제물포구' where sido = '인천광역시' and sigungu = '동구';
update core.items set sigungu = case
    when address ~ '(검단|불로|마전|당하|원당|대곡|오류|왕길|금곡|백석|아라)동' then '검단구' else '서해구' end
  where sido = '인천광역시' and sigungu = '서구';

drop table cw;
drop table cwc;
