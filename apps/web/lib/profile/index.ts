// 시작 질문 답 (로그인 전에는 이 기기에만 저장). 저장이 안 되는 브라우저에서도 화면은 동작.
export type Purpose = "live" | "rent" | "resell";
export type Profile = {
  regions: string[];
  cash: number | null;
  purpose: Purpose | null;
  homes?: number | null; // 지금 가진 집 수(계산 화면에서 한 번 물음)
  firstTime?: boolean;
  selling?: boolean; // 1채일 때 기존 집 팔 계획
};

const KEY = "aucs_profile";
const SENT_KEY = "aucs_profile_sent";
export type ProfileBody = { regions: string[]; cash: number | null; purpose: Purpose | null };

export function loadProfile(): Profile | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Profile) : null;
  } catch {
    return null;
  }
}

export function saveProfile(p: Profile): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(p));
  } catch {
    /* 저장 못 해도 계속 */
  }
}

// 내 조건을 계정에 옮겨 둠(11/8 한 곳 — 예전엔 홈 화면에서만 해서 다른 화면으로 들어오면 안 옮겨졌음).
// 로그인한 상태로 어느 화면에서든 한 번, 바뀐 게 없으면 다시 보내지 않음.
export function pushProfile(token: string, send: (body: ProfileBody) => Promise<unknown>): void {
  const p = loadProfile();
  if (!p) return;
  const body: ProfileBody = { regions: p.regions, cash: p.cash, purpose: p.purpose };
  const sig = JSON.stringify(body);
  try {
    if (localStorage.getItem(SENT_KEY) === sig) return;
  } catch {}
  send(body)
    .then(() => {
      try {
        localStorage.setItem(SENT_KEY, sig);
      } catch {}
    })
    .catch(() => {});
}
