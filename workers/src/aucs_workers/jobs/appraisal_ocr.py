"""손님이 올린 그림 감정평가서: 글자 인식으로 사건번호가 맞으면 바로 넣고 포인트(11/14 대표님).

못 읽었거나 다른 사건번호만 보이면 그대로 관리자 확인에 둠(까닭을 적어 둠 — 다시 읽지 않음).
「관리자_요청」 작업(5분마다)이 함께 부름. 할 일이 없으면 바로 끝남.

    uv run python -m aucs_workers.jobs.appraisal_ocr
"""


def main() -> int:
    from aucs_api.services import points  # PC 는 한 저장소라 API 코드를 그대로 씀

    from aucs_workers.extract.appraisal_pdf import case_numbers, same_case
    from aucs_workers.extract.pdf_ocr import ocr_head

    rows = points.ocr_waiting()
    for r in rows:
        raw = points.review_pdf(r["contrib_id"])
        if raw is None:
            print(f"── 감정평가서 {r['contrib_id']}: 원본을 못 받음", flush=True)
            continue
        text = ocr_head(raw)
        ok = same_case(text, r["case_no"])
        why = "ok" if ok else ("ocr_other" if case_numbers(text) else "ocr_none")
        print(f"── 감정평가서 글자 인식 {r['contrib_id']} · {r['case_no']} → {why}", flush=True)
        points.ocr_settle(r["contrib_id"], ok, why)
    return len(rows)


if __name__ == "__main__":
    main()
