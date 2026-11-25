-- 11/25 대표님: 지난 물건은 굳히고, 세법 · 대출 기준이 바뀌면 걸리는 물건만 다시 셈.
--   기준표 줄의 값이 고쳐진 시각(changed_at)을 남겨, 분석이 「쓴 줄이 그 뒤 고쳐졌는지」로 다시 돌릴 물건을 고름.
--   새 줄을 넣는 것(시행일이 다른 줄)은 시행일로 고르므로 이 칸 없이도 잡힘.
alter table ref.rule_tables add column if not exists changed_at timestamptz not null default now();

create or replace function ref.rule_tables_touch() returns trigger language plpgsql as $$
begin
  if new.value is distinct from old.value or new.valid_from is distinct from old.valid_from then
    new.changed_at := now();
  end if;
  return new;
end $$;

drop trigger if exists rule_tables_touch on ref.rule_tables;
create trigger rule_tables_touch before update on ref.rule_tables
  for each row execute function ref.rule_tables_touch();
