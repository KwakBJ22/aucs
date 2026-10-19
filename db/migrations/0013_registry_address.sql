-- 0013: 올린 등기부의 소재지와 「그래도 이 등기부로 보기」 (10/19)
alter table app.uploaded_registries add column if not exists address text, add column if not exists address_ok boolean not null default false;
comment on column app.uploaded_registries.address is '등기부 첫 장의 소재지(읽은 그대로)';
comment on column app.uploaded_registries.address_ok is '주소가 달라도 손님이 「그래도 이 등기부로 보기」를 누름';
