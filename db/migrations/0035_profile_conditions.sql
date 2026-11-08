-- 0035 (11/8 대표님): 내 조건을 계정에 그대로 — 다른 기기로 로그인해도 같은 조건.
-- 예전엔 목적을 「실거주·투자」 둘로만 저장해 임대·매도를 잃었고, 가진 집 수(계산 화면)는 기기에만 있었음.
-- 'invest' 는 예전 줄을 그대로 두려고 남김(새로 저장할 땐 rent·resell).
alter table app.profiles drop constraint if exists profiles_purpose_check;
alter table app.profiles add constraint profiles_purpose_check
  check (purpose in ('live', 'rent', 'resell', 'invest'));
alter table app.profiles add column if not exists homes smallint check (homes between 0 and 2);
alter table app.profiles add column if not exists first_time boolean;
alter table app.profiles add column if not exists selling boolean;
