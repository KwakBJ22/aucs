-- 0003 매각결과 종류 넓히기 (낙찰결과_공개 옮기기용)
alter table core.sale_results drop constraint sale_results_result_check;
alter table core.sale_results add constraint sale_results_result_check
  check (result in ('sold','failed','changed','withdrawn','dismissed'));
comment on column core.sale_results.result is 'sold 매각(대납 포함) / failed 유찰 / changed 변경 / withdrawn 취하 / dismissed 기각·각하';
comment on column core.sale_results.origin is '내부용 출처: court_collect 법원수집 / court_db 법원DB / supplement 보충(법원 매각결과와 같은 칸만)';
