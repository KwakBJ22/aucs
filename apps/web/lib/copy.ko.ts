// 화면 문구는 이 파일 한 곳에 모읍니다.
export const copy = {
  appName: "옥스",
  health: {
    api: "API 연결",
    db: "DB 연결",
    checking: "확인 중",
    ok: "정상",
    fail: "안 됨",
  },
  admin: {
    title: "관리자",
    tokenLabel: "관리자 열쇠",
    tokenSave: "열기",
    denied: "열쇠가 맞지 않아요",
    jobs: "수집 상태",
    job: "작업",
    lastRun: "마지막 실행",
    result: "결과",
    count: "건수",
    never: "아직 없음",
    db: "DB 용량",
    review: "확인 기다리는 것",
    reviewEmpty: "없어요",
    flags: "자료 공개 설정",
    rules: "기준표",
    rulesEmpty: "아직 넣지 않았어요",
    statusName: { ok: "정상", failed: "오류", stopped: "멈춤", running: "도는 중" } as Record<
      string,
      string
    >,
  },
} as const;
