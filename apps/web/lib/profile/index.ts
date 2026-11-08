// 내 조건(시작 질문 답 + 계산 화면의 가진 집 수). 이 기기에 저장하고, 로그인하면 계정과 맞춤(11/8 한 곳).
// 저장이 안 되는 브라우저에서도 화면은 동작.
export type Purpose = "live" | "rent" | "resell";
export type Profile = {
  regions: string[];
  cash: number | null;
  purpose: Purpose | null;
  homes?: number | null; // 지금 가진 집 수(계산 화면에서 한 번 물음)
  firstTime?: boolean;
  selling?: boolean; // 1채일 때 기존 집 팔 계획
  at?: string; // 마지막으로 바꾼 시각(ISO) — 계정 것과 어느 쪽이 새것인지 견줌
};
export type ServerProfile = Profile & { at: string | null };

const KEY = "aucs_profile";
const SENT_KEY = "aucs_profile_sent";

export function loadProfile(): Profile | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Profile) : null;
  } catch {
    return null;
  }
}

// 바꾼 시각을 함께 남김(계정과 맞출 때 새것이 이기게). at 을 주면 그 시각 그대로(계정에서 되살릴 때).
export const PROFILE_EVENT = "aucs-profile";
export function saveProfile(p: Profile, at?: string): void {
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...p, at: at ?? new Date().toISOString() }));
  } catch {
    /* 저장 못 해도 계속 */
  }
  // 로그인 중이면 계정에도 올리도록 알림(Providers 의 ProfileSync 가 받음). 되살릴 때(at 있음)는 안 알림
  if (!at && typeof window !== "undefined") window.dispatchEvent(new Event(PROFILE_EVENT));
}

const body = (p: Profile) => ({
  regions: p.regions,
  cash: p.cash,
  purpose: p.purpose,
  homes: p.homes ?? null,
  firstTime: p.firstTime ?? null,
  selling: p.selling ?? null,
});

// 로그인했을 때 이 기기와 계정의 내 조건을 맞춤(어느 화면으로 들어와도 Providers 한 곳에서, 11/8).
// 계정 것이 더 새것이면(새 기기·다른 기기에서 바꿈) 이 기기에 되살리고 true, 아니면 이 기기 것을 계정에 올림.
export async function syncProfile(
  get: () => Promise<ServerProfile | null>,
  put: (b: ReturnType<typeof body>) => Promise<unknown>,
): Promise<boolean> {
  const local = loadProfile();
  const server = await get().catch(() => null);
  // 시각이 없는 예전 기기 저장값은 이 기기 것을 믿음(계정의 예전 줄은 목적이 둘뿐이라 덮으면 잃음)
  if (server && (!local || (server.at && local.at && server.at > local.at))) {
    const { at, ...rest } = server;
    saveProfile(rest, at ?? undefined);
    try {
      localStorage.setItem(SENT_KEY, JSON.stringify(body(rest)));
    } catch {}
    return JSON.stringify(local ? body(local) : null) !== JSON.stringify(body(rest));
  }
  if (!local) return false;
  const sig = JSON.stringify(body(local));
  try {
    if (localStorage.getItem(SENT_KEY) === sig) return false; // 바뀐 게 없으면 다시 보내지 않음
  } catch {}
  await put(body(local))
    .then(() => {
      try {
        localStorage.setItem(SENT_KEY, sig);
      } catch {}
    })
    .catch(() => {});
  return false;
}
