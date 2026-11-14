-- 0055 관리자 「오늘」 하실 일(11/14 대표님): 실패한 작업을 「확인함」으로 넘길 수 있게.
-- 손으로 한 번 돌린 작업(감정평가서 폴더 등)이 실패하면 다시 돌리기 전까지 빨간 불이 계속 남았음.
alter table ops.job_runs add column if not exists acked_at timestamptz;
comment on column ops.job_runs.acked_at is '관리자가 실패·멈춤을 확인한 때 — 빨간 불에서 뺌(기록은 그대로)';
-- 옛 문구 바로잡기: 감정평가서는 11/12 부터 가리지 않고 그대로 보임(켜고 끄는 값은 건드리지 않음)
update app.feature_flags set note = '감정평가서 표시 — 지금은 안 쓰는 스위치(11/12 부터 원본 그대로 보임)'
 where flag_key = 'show_appraisal_report' and note like '%협회 확인 전%';
