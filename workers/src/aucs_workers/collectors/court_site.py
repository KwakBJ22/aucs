"""법원경매정보 사이트와 대화하는 부분. 화면이 보내는 요청과 같은 모양만 보냅니다(로그인 없음).

요청 모양은 지금 시스템(D:\\Auction\\system\\collectors\\court_auction.py)에서 그대로 옮겼습니다.
"""

from collections.abc import Iterator
from typing import Any

from aucs_workers.collectors.browser import launch_chrome
from aucs_workers.collectors.polite import Polite

COURTS = {
    "B000210": "서울중앙", "B000211": "서울동부", "B000215": "서울서부", "B000212": "서울남부",
    "B000213": "서울북부", "B000214": "의정부", "B214807": "고양", "B214804": "남양주",
    "B000241": "부천", "B000250": "수원", "B000251": "성남", "B000252": "여주",
    "B000253": "평택", "B250826": "안산", "B000254": "안양", "B000240": "인천",
}  # fmt: skip
PAGE_SIZE = 50  # 100 은 오류
SEARCH_PAGE = "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml"
RESULT_PAGE = "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ158M00.xml"

_PARSE = """
  const text = await r.text();
  try {
    const j = JSON.parse(text);
    if (j.data && j.data.dlt_srchResult)
      return { ok: true, total: +j.data.dma_pageInfo.totalCnt, rows: j.data.dlt_srchResult };
    return { ok: false, status: r.status, msg: text.slice(0, 300) };
  } catch (e) { return { ok: false, status: r.status, msg: text.slice(0, 300) }; }
}"""

JS_ITEMS = (
    r"""
async ([cd, page, size, from, to]) => {
  const K = "aeeEvlAmtMax aeeEvlAmtMin carMdlNm carMdyrMax carMdyrMin cortAuctnMbrsId csNo dspslDxdyYmd dspslPlcNm execrOfcDvsCd flbdNcntMax flbdNcntMin fothDspslHm fstDspslHm fuelKndCd gdsVendNm grbxTypCd jdbnCd lafjOrderBy lclDspslGdsLstUsgCd lwsDspslPrcMax lwsDspslPrcMin lwsDspslPrcRateMax lwsDspslPrcRateMin mclDspslGdsLstUsgCd mvprpArtclKndCd mvprpArtclNm mvprpAtchmPlcTypCd mvprpDspslPlcAdongEmdCd mvprpDspslPlcAdongSdCd mvprpDspslPlcAdongSggCd objctArDtsMax objctArDtsMin rdDspslPlcAdongEmdCd rdDspslPlcAdongSdCd rdDspslPlcAdongSggCd rdnmNo rdnmSdCd rdnmSggCd rletDspslSpcCondCd rprsAdongEmdCd rprsAdongSdCd rprsAdongSggCd sclDspslGdsLstUsgCd scndDspslHm sideDvsCd thrdDspslHm".split(' ');
  const info = {}; K.forEach(k => info[k] = "");
  Object.assign(info, { bidDvsCd: "000331", mvprpRletDvsCd: "00031R", cortAuctnSrchCondCd: "0004601",
    notifyLoc: "off", pgmId: "PGJ151F01", cortStDvs: "1", statNum: 1,
    cortOfcCd: cd, bidBgngYmd: from, bidEndYmd: to });
  const body = { dma_pageInfo: { pageNo: page, pageSize: size, bfPageNo: page > 1 ? page - 1 : 1,
      startRowNo: (page - 1) * size + 1, totalCnt: "", totalYn: "Y", groupTotalCount: "" },
    dma_srchGdsDtlSrchInfo: info };
  const r = await fetch('/pgj/pgjsearch/searchControllerMain.on', { method: 'POST',
    headers: { 'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/json' },
    body: JSON.stringify(body), credentials: 'include' });
"""
    + _PARSE
)

JS_RESULTS = (
    r"""
async ([cd, page, size]) => {
  const info = { statNum: "3", pgmId: "PGJ158M01", cortStDvs: "1", cortOfcCd: cd };
  "jdbnCd csNo rprsAdongSdCd rprsAdongSggCd rprsAdongEmdCd rdnmSdCd rdnmSggCd rdnmNo auctnGdsStatCd lclDspslGdsLstUsgCd mclDspslGdsLstUsgCd sclDspslGdsLstUsgCd dspslAmtMin dspslAmtMax aeeEvlAmtMin aeeEvlAmtMax flbdNcntMin flbdNcntMax lafjOrderBy"
    .split(' ').forEach(k => info[k] = "");
  const body = { dma_pageInfo: { pageNo: page, pageSize: size, bfPageNo: page > 1 ? page - 1 : "",
      startRowNo: page > 1 ? (page - 1) * size + 1 : "", totalCnt: "", totalYn: "Y", groupTotalCount: "" },
    dma_srchGdsDtlSrchInfo: info };
  const r = await fetch('/pgj/pgjsearch/selectDspslSchdRsltSrch.on', { method: 'POST',
    headers: { 'Content-Type': 'application/json;charset=UTF-8', 'Accept': 'application/json' },
    body: JSON.stringify(body), credentials: 'include' });
"""
    + _PARSE
)


def fetch_pages(
    courts: dict[str, str],
    polite: Polite,
    *,
    results: bool,
    date_from: str = "",
    date_to: str = "",
    show: bool = False,
) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """법원마다 모든 쪽을 받아 (법원코드, 행들) 을 차례로 돌려줍니다."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = launch_chrome(p, headless=not show)
        page = browser.new_page()
        page.goto(RESULT_PAGE if results else SEARCH_PAGE, wait_until="networkidle", timeout=60000)
        try:
            for cd, name in courts.items():
                pg, got = 1, 0
                while True:

                    def one(cd: str = cd, pg: int = pg) -> dict[str, Any]:
                        if results:
                            return dict(page.evaluate(JS_RESULTS, [cd, pg, PAGE_SIZE]))
                        return dict(
                            page.evaluate(JS_ITEMS, [cd, pg, PAGE_SIZE, date_from, date_to])
                        )

                    res = polite.call(one, f"{name} {pg}쪽")
                    rows: list[dict[str, Any]] = res["rows"]
                    yield cd, rows
                    got += len(rows)
                    if not rows or got >= int(res["total"]):
                        break
                    pg += 1
                polite.between_cases()
        finally:
            browser.close()
