"""그림으로 된 등기부 PDF 글자 인식(11/3): Vercel 에는 글자 인식 프로그램(tesseract)이 없어 PC 가 마저 읽음.

「관리자_요청」 작업(5분마다)이 함께 부름. 할 일이 없으면 바로 끝남.

    uv run python -m aucs_workers.jobs.registry_ocr
"""


def main() -> int:
    from aucs_api.services import registry  # PC 는 한 저장소라 API 코드를 그대로 씀

    ids = registry.ocr_waiting()
    for upload_id in ids:
        print(f"── 등기부 글자 인식 {upload_id}", flush=True)
        registry.parse_upload(upload_id, ocr=True)
    return len(ids)


if __name__ == "__main__":
    main()
