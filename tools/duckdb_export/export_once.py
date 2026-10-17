"""로컬 DuckDB → Supabase 한 번 옮기기 (대표님 PC에서 실행).

옮기는 것 (10/17 대표님 결정)
- 법정동코드 → ref.regions, 철도역 → ref.stations
- 낙찰결과_공개 전부 → core.sale_results (법원 매각결과와 같은 칸만, 출처는 내부용 origin)
- 실거래 매매 전부 + 전월세 최근 1년 → core.trades

다시 실행해도 같은 결과가 되도록 표마다 비우고 다시 넣습니다(trades·regions·stations),
매각결과는 같은 사건·물건·기일이 있으면 건너뜁니다.

    uv run --with duckdb python tools/duckdb_export/export_once.py
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
DUCK = os.getenv("AUCTION_DB", "D:/Auction/duckdb/data.duckdb")

COURT_CODE = {
    "서울중앙": "B000210", "서울동부": "B000211", "서울서부": "B000215", "서울남부": "B000212",
    "서울북부": "B000213", "의정부": "B000214", "고양": "B214807", "남양주": "B214804",
    "부천": "B000241", "수원": "B000250", "성남": "B000251", "여주": "B000252",
    "평택": "B000253", "안산": "B250826", "안양": "B000254",
}  # fmt: skip
RESULT = {"매각": "sold", "대납": "sold", "유찰": "failed", "변경": "changed", "취하": "withdrawn",
          "기각": "dismissed", "각하": "dismissed"}  # fmt: skip
ORIGIN = {"법원수집": "court_collect", "법원DB": "court_db", "보충": "supplement"}
PROP = {"아파트": "apt", "연립다세대": "rowhouse", "오피스텔": "officetel", "단독다가구": "house",
        "상업업무용": "commercial"}  # fmt: skip


def copy_rows(cur: psycopg.Cursor, sql: str, rows: list[tuple]) -> int:
    with cur.copy(sql) as cp:
        for r in rows:
            cp.write_row(r)
    return len(rows)


def main() -> None:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        sys.exit("DATABASE_URL 이 비어 있습니다 (.env)")
    duck = duckdb.connect(DUCK, read_only=True)
    with psycopg.connect(url) as pg, pg.cursor() as cur:
        # 1) 법정동
        rows = duck.execute(
            "select 법정동코드, case 단위 when '시도' then 'sido' when '시군구' then 'sigungu' else 'dong' end,"
            " 시도, 시군구, 읍면동, 시군구코드, 전체명 from 법정동코드"
        ).fetchall()
        cur.execute("delete from ref.regions")
        n = copy_rows(
            cur,
            "copy ref.regions (region_code, level, sido, sigungu, eupmyeondong, sigungu_code, full_name) from stdin",
            rows,
        )
        print(f"법정동 {n:,}")

        # 2) 철도역
        rows = duck.execute(
            "select 역명, 노선명, 운영기관, 'SRID=4326;POINT(' || 경도 || ' ' || 위도 || ')', try_cast(nullif(폐지일자,'') as date)"
            " from 철도역 where 위도 is not null and 경도 is not null"
        ).fetchall()
        cur.execute("delete from ref.stations")
        n = copy_rows(
            cur,
            "copy ref.stations (name_ko, line_name, operator, geom, closed_date) from stdin",
            rows,
        )
        print(f"철도역 {n:,}")
        pg.commit()

        # 3) 낙찰 결과 (공개용 표)
        src = duck.execute(
            "select 법원, 사건번호, 물건번호, 매각기일, 용도, 소재지, 시도, 감정가_원, 최저가_원, 매각가_원,"
            " 매각가율, 유찰횟수, 결과, 출처 from 낙찰결과_공개"
        ).fetchall()
        rows = []
        for (
            court,
            case_no,
            item_no,
            d,
            usage,
            addr,
            sido,
            app,
            mn,
            win,
            rate,
            failed,
            res,
            origin,
        ) in src:
            code = COURT_CODE.get(court)
            if not code or res not in RESULT:
                continue
            item_no = item_no or 1
            rows.append(
                (
                    code,
                    case_no,
                    item_no,
                    d,
                    f"{code}-{case_no}-{item_no}",
                    usage,
                    addr,
                    sido,
                    app,
                    mn,
                    win if RESULT[res] == "sold" else None,
                    rate,
                    failed,
                    RESULT[res],
                    "지분" in (addr or ""),
                    ORIGIN.get(origin, "supplement"),
                )
            )
        cur.execute(
            "create temp table _sr (like core.sale_results including defaults) on commit drop"
        )
        copy_rows(cur, "copy _sr (court_code, case_no, item_no, sale_date, item_id, usage_name, address, sido,"
                       " appraisal_krw, min_price_krw, winning_bid_krw, sale_rate, failed_count, result, is_share, origin)"
                       " from stdin", rows)  # fmt: skip
        cur.execute(
            "insert into core.sale_results (court_code, case_no, item_no, sale_date, item_id, usage_name, address,"
            " sido, appraisal_krw, min_price_krw, winning_bid_krw, sale_rate, failed_count, result, is_share,"
            " origin, fetched_at) select court_code, case_no, item_no, sale_date, item_id, usage_name, address,"
            " sido, appraisal_krw, min_price_krw, winning_bid_krw, sale_rate, failed_count, result, is_share,"
            " origin, now() from _sr on conflict do nothing"
        )
        print(f"낙찰 결과 {cur.rowcount:,} / {len(rows):,}")
        pg.commit()

        # 4) 실거래: 매매 전부 + 전월세 최근 1년
        cur.execute("delete from core.trades")
        sale = duck.execute(
            "select 유형, 세부유형, 시군구코드, 법정동코드, 법정동, 단지명, 지번, 면적, 대지면적, 층, 건축년도,"
            " 계약일, 거래금액_원 from 실거래_매매"
        ).fetchall()
        n = copy_rows(cur, "copy core.trades (deal_kind, prop_type, sub_type, sigungu_code, region_code, dong_name,"
                           " complex_name, lot_no, area_m2, land_area_m2, floor, build_year, deal_date, price_krw)"
                           " from stdin", [("sale", PROP.get(r[0], r[0]), *r[1:]) for r in sale])  # fmt: skip
        print(f"실거래 매매 {n:,}")
        since = date.today() - timedelta(days=365)
        lease = duck.execute(
            "select 유형, 세부유형, 시군구코드, 법정동코드, 법정동, 단지명, 지번, 면적, 층, 건축년도, 계약일,"
            " 보증금_원, 월세_원, 계약구분, 종전보증금_원 from 실거래_전월세 where 계약일 >= ?",
            [since],
        ).fetchall()
        n = copy_rows(cur, "copy core.trades (deal_kind, prop_type, sub_type, sigungu_code, region_code, dong_name,"
                           " complex_name, lot_no, area_m2, floor, build_year, deal_date, deposit_krw,"
                           " monthly_rent_krw, contract_kind, prev_deposit_krw) from stdin",
                      [("lease", PROP.get(r[0], r[0]), *r[1:]) for r in lease])  # fmt: skip
        print(f"실거래 전월세(1년) {n:,}")
        pg.commit()
        cur.execute("select pg_size_pretty(pg_database_size(current_database()))")
        print("DB 크기", cur.fetchone()[0])
    print("끝")


if __name__ == "__main__":
    main()
