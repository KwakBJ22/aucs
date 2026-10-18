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
