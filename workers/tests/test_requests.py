"""관리자 「다시 돌리기 요청」 이름 → 명령(11/2)."""


def test_request_command() -> None:
    from aucs_workers.jobs.requests import command

    assert command("daily")[-1] == "daily"
    assert command("analyze_item:B1-2024타경1-1")[-1] == "B1-2024타경1-1"
    assert command("rm -rf") is None
