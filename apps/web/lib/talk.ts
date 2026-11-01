// 말로 찾기: 「수지 30평대 7억 이하 아파트」 → 조건 칩. 규칙으로만 읽고(AI 아님), 못 읽은 말은 그대로 검색어로 남김.
import type { FindFilter, Source } from "@/lib/api/items";

export type TalkPart = { key: string; label: string };
export type Talk = {
  sigungu?: string[];
  source?: Source;
  filter: FindFilter;
  parts: TalkPart[]; // 칩(지우면 그 조건만 빠짐)
  rest: string; // 남은 말(단지·동네 검색)
};

const EOK = 100_000_000;
const PY = 3.3058;
const NET = 0.76; // 「30평대」는 보통 공급 평형 → 전용으로 바꿀 때 대략 비율

const USAGE: [RegExp, string, string][] = [
  [/아파트/, "apt", "아파트"],
  [/빌라|다세대|연립/, "villa", "빌라"],
  [/오피스텔/, "officetel", "오피스텔"],
  [/단독|다가구|주택/, "house", "주택"],
  [/상가|사무실|점포|근린/, "shop", "상가·사무실"],
  [/토지|땅|대지|임야/, "land", "땅"],
];

function money(num: string, unit: string): number | null {
  const n = Number(num.replace(/,/g, ""));
  if (!Number.isFinite(n)) return null;
  if (unit === "억") return Math.round(n * EOK);
  if (unit === "천") return Math.round(n * 10_000_000);
  if (unit === "만") return Math.round(n * 10_000);
  return null;
}

function regionOf(word: string, names: string[]): string | null {
  const w = word.replace(/(특별시|광역시|시|군|구)$/, "");
  if (w.length < 2) return null;
  // 「수지」→「용인시 수지구」, 「강남」→「강남구」, 「성남」→「성남시 …」은 첫 것
  const hit = names.find((n) => n.split(" ").some((p) => p.replace(/(시|군|구)$/, "") === w));
  return hit ?? null;
}

export function parseTalk(text: string, regionNames: string[]): Talk | null {
  let s = ` ${text.trim()} `;
  const out: Talk = { filter: {}, parts: [], rest: "" };
  const take = (re: RegExp, fn: (m: RegExpMatchArray) => boolean) => {
    const m = s.match(re);
    if (m && fn(m)) s = s.replace(m[0], " ");
  };
  // 금액: 7억 이하 · 7억 5천 이하 · 5천만원까지 · 3억 미만
  take(
    /(\d+(?:\.\d+)?)\s*억(?:\s*(\d+)\s*천)?\s*(?:만\s*)?원?\s*(이하|까지|미만|아래|안쪽)/,
    (m) => {
      const v = Math.round(Number(m[1]) * EOK + (m[2] ? Number(m[2]) * 10_000_000 : 0));
      out.filter.price_max = v;
      out.parts.push({
        key: "price_max",
        label: `최저가 ${m[1]}억${m[2] ? ` ${m[2]}천` : ""} 이하`,
      });
      return true;
    },
  );
  take(/([\d,]+)\s*(천|만)\s*(?:만\s*)?원?\s*(이하|까지|미만|아래)/, (m) => {
    const v = money(m[1] ?? "", m[2] === "천" ? "천" : "만");
    if (!v) return false;
    out.filter.price_max = v;
    out.parts.push({ key: "price_max", label: `최저가 ${m[1]}${m[2]} 이하` });
    return true;
  });
  // 면적: 30평대 · 25평 · 84㎡ · 전용 84
  take(/(\d{1,2})0\s*평대/, (m) => {
    const lo = Number(m[1]) * 10;
    out.filter.area_min = Math.round(lo * PY * NET);
    out.filter.area_max = Math.round((lo + 10) * PY * NET);
    out.parts.push({
      key: "area",
      label: `${lo}평대(전용 ${out.filter.area_min}~${out.filter.area_max}㎡)`,
    });
    return true;
  });
  take(/(?:전용\s*(\d{2,3})\s*(?:㎡|m2|제곱)?|(\d{2,3})\s*(?:㎡|m2|제곱|형))/, (m) => {
    const v = Number(m[1] ?? m[2]);
    out.filter.area_min = v - 4;
    out.filter.area_max = v + 4;
    out.parts.push({ key: "area", label: `전용 ${v}㎡ 안팎` });
    return true;
  });
  // 유찰: 2번 유찰 · 유찰 2회 이상
  take(/(?:(\d)\s*(?:번|회)\s*(?:이상\s*)?유찰|유찰\s*(\d)\s*(?:번|회)\s*(?:이상)?)/, (m) => {
    const n = Number(m[1] ?? m[2]);
    out.filter.failed_min = n;
    out.parts.push({ key: "failed_min", label: `유찰 ${n}번 이상` });
    return true;
  });
  // 기간: 이번 주 · 일주일 · 2주 안
  take(/(이번\s*주|일주일|1주)/, () => {
    out.filter.days_max = 7;
    out.parts.push({ key: "days_max", label: "1주 안 입찰" });
    return true;
  });
  take(/(\d)\s*주\s*(?:안|이내)?/, (m) => {
    out.filter.days_max = Number(m[1]) * 7;
    out.parts.push({ key: "days_max", label: `${m[1]}주 안 입찰` });
    return true;
  });
  // 경매·공매
  take(/\s(공매|경매)만?\s/, (m) => {
    out.source = m[1] === "공매" ? "onbid" : "court";
    out.parts.push({ key: "source", label: m[1] ?? "" });
    return true;
  });
  // 종류
  for (const [re, key, label] of USAGE) {
    take(new RegExp(`\\s(${re.source})\\S*`), () => {
      out.filter.usage = [...(out.filter.usage ?? []), key];
      out.parts.push({ key: `usage:${key}`, label });
      return true;
    });
  }
  // 지역: 남은 낱말 중 시군구 이름과 맞는 것
  const words = s.split(/\s+/).filter(Boolean);
  const left: string[] = [];
  for (const w of words) {
    const r = regionOf(w, regionNames);
    if (r && !(out.sigungu ?? []).includes(r)) {
      out.sigungu = [...(out.sigungu ?? []), r];
      out.parts.push({ key: `region:${r}`, label: r });
    } else left.push(w);
  }
  out.rest = left.join(" ");
  return out.parts.length ? out : null;
}

// 칩 하나 지우기
export function dropPart(t: Talk, key: string): Talk | null {
  const f: FindFilter = { ...t.filter };
  let sigungu = t.sigungu;
  let source = t.source;
  if (key === "price_max") delete f.price_max;
  if (key === "area") {
    delete f.area_min;
    delete f.area_max;
  }
  if (key === "failed_min") delete f.failed_min;
  if (key === "days_max") delete f.days_max;
  if (key === "source") source = undefined;
  if (key.startsWith("usage:")) f.usage = (f.usage ?? []).filter((u) => `usage:${u}` !== key);
  if (key.startsWith("region:")) sigungu = (sigungu ?? []).filter((r) => `region:${r}` !== key);
  const parts = t.parts.filter((p) => p.key !== key);
  if (!parts.length) return null;
  return { ...t, filter: f, sigungu: sigungu?.length ? sigungu : undefined, source, parts };
}

// 「버들치마을성복힐스테이트3차 304동 2층203호」 → 단지 이름만(동·층·호 뺌)
export function complexName(d: { building: string | null; place: string | null }): string {
  const b = (d.building ?? "").replace(/\s*(제?\d+동|[^\s]*\d+층|[^\s]*\d+호).*$/, "").trim();
  return b || d.place || "";
}
