-- 0020 명도비·수리비 대략치 기준표(할 일 2). MCP로 넣음(10/27). 값은 개발 기준 — 검토 요청서 대상.
insert into ref.rule_tables (rule_key, valid_from, value, basis) values (
  'move_out_repair', '2026-10-27',
  '{"move_out": {"per_pyeong_krw": [50000, 150000], "min_krw": [1500000, 3000000],
                 "no_elevator_from_floor": 3, "no_elevator_add_pct": 30},
    "repair": {"bands": [[10, [0, 100000]], [20, [100000, 300000]], [30, [300000, 600000]], [999, [600000, 1000000]]],
               "unknown": [100000, 600000]}}'::jsonb,
  '명도비 = 협의 이사비(아래)~강제집행 노무·보관(위) 대략, 전용 평 기준·최소액, 승강기 없이 3층 이상이면 위쪽 30% 더. 수리비 = 사용승인 연식별 실내 수리 평당 범위, 연식 모르면 넓은 범위. [검토 전 — 개발 기준]'
) on conflict do nothing;
