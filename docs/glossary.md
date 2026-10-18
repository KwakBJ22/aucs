# 용어사전 (영어 이름 ↔ 한글)

코드·DB에 쓰는 영어 이름은 이 사전에만 정합니다. 새 이름은 먼저 여기에 추가합니다.

## 경매 용어
| 영어 | 한글 |
|---|---|
| case | 사건 (법원코드 + 사건번호) |
| item | 매각 물건 (사건 + 물건번호) |
| item_part | 물건 구성 (토지·건물·전유) |
| round | 매각 회차 (물건 + 매각기일) |
| sale_date | 매각기일 |
| appraisal_krw | 감정가 |
| min_price_krw | 최저매각가격 |
| failed_round | 유찰 |
| sale_result | 매각결과 |
| winning_bid_krw | 낙찰가 |
| sale_rate | 낙찰가율 |
| bidder_count | 응찰자수 |
| base_right | 말소기준권리 |
| opposing_power | 대항력 |
| priority_repayment | 우선변제권 |
| top_priority_repayment | 최우선변제 (소액임차) |
| claim_deadline | 배당요구종기 |
| distribution | 배당 |
| spec_sheet | 매각물건명세서 |
| status_report | 현황조사서 |
| appraisal_report | 감정평가서 (화면 숨김) |
| case_event | 문건·송달 내역 |
| registry | 등기부 (갑구·을구) |
| tenant | 임차인 |
| move_in_date | 전입일 |
| fixed_date | 확정일자 |
| lien | 유치권 |
| statutory_superficies | 법정지상권 |
| share_sale | 지분 매각 |
| special_sale_condition | 특별매각조건 |
| eviction | 명도 |
| is_special_case | 특수 사건 (지분·유치권·선순위 임차인·법정지상권) |
| pnu | 필지고유번호 (19자리) |
| complex | 단지 (법정동코드 + 본번 + 부번) |
| trade | 실거래 |
| building | 건축물대장 |
| price_notice | 공시가격 |
| land_use | 토지이용계획 |
| redev_zone | 정비사업 구역 |

## 자료 관리
| 영어 | 한글 |
|---|---|
| source_id | 원천 |
| fetched_at | 받은 시각 |
| source_date | 원문 작성일 |
| checked_at | 마지막으로 변경을 확인한 시각 |
| computed_at | 계산한 시각 |
| display_policy | 외부 표시: public(출처 표시) / owner_only(올린 본인) / internal(내부만) / blocked |
| checksum | 같은 내용 확인용 |
| check_status | 추출값 검증: auto_ok / needs_review / confirmed / rejected |
| data_status | 자료 상태: missing 미확보 / fetching 받는 중 / fetched 확보 / extracted 확보 / needs_review 확인 필요 / verified (표시 없음) / stale 오래됨 / error 오류 / restricted 표시 안 함 |
| engine_version | 분석 규칙 버전 (rules-x.y.z) |
| input_hash | 계산 입력값 해시 (재현용) |

## 스키마와 표
| 스키마 | 표 | 한글 |
|---|---|---|
| raw | court_item_raw | 법원 물건 원본 |
| raw | court_doc_raw | 법원 문서 원본 |
| raw | court_result_raw | 법원 매각결과 원본 |
| raw | trade_raw / building_raw / price_notice_raw / land_use_raw | 실거래 / 건축물대장 / 공시가격 / 토지이용계획 원본 |
| ref | sources | 원천 목록·이용조건 |
| ref | regions | 법정동 |
| ref | courts | 법원 |
| ref | stations | 철도역 |
| ref | redev_zones | 정비사업 구역 |
| ref | rule_tables | 기준표 (소액임차·상가 환산보증금 한도·세율·LTV, 적용 시작일·끝날·근거) |
| ref | holidays | 공휴일 (법원 기한 계산, checked=확인된 날만 씀) |
| core | cases / items / item_parts / rounds | 사건 / 물건 / 물건 구성 / 회차 |
| core | documents / extracted_fields | 문서 / 문서에서 뽑은 값 |
| core | rights / tenants / case_events | 권리 / 임차인 / 문건·송달 |
| core | trades / buildings / complexes / sale_results | 실거래 / 건축물 / 단지 / 매각결과 |
| analysis | item_analysis / right_judgments / price_estimates / comparables | 물건 분석(버전) / 권리 판정 / 시세 추정 / 비교 거래 |
| analysis | risk_signals / cost_baselines / item_data_status | 위험 신호 / 비용 기준 / 자료 상태 |
| app | users / profiles | 회원 / 프로필(관심 지역·현금·목적) |
| app | subscriptions / payments | 이용권 / 결제 |
| app | watch_items / watch_steps / notes / attachments / scenarios | 관심 물건 / 단계 / 메모 / 첨부 / 계산 시나리오 |
| app | saved_searches / alert_events / notifications | 저장한 조건 / 보낸 알림 / 알림함 |
| app | compare_exclusions / mock_bids / bid_results | 비교함에서 뺀 물건 / 모의입찰 / 입찰 결과 기록 |
| app | uploaded_registries / feature_flags | 올린 등기부 / 기능 켜기·끄기 |
| ops | jobs / job_runs / fetch_log / audit_log | 작업 / 작업 실행 / 수집 기록 / 관리자 변경 기록 |
