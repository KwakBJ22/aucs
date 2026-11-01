import { copy } from "@/lib/copy.ko";
import { won } from "@/lib/format";

// 저장한 조건을 한 줄로(11/1): 예전엔 이름이 모두 「내 조건」이라 무엇을 저장했는지 알 수 없었음
export function condSummary(f: Record<string, unknown>): string {
  const out: string[] = [];
  const sg = f.sigungu as string[] | undefined;
  if (sg?.length) out.push(sg.join("·"));
  const us = f.usage as string[] | undefined;
  if (us?.length) out.push(us.map((u) => copy.find.usages[u] ?? u).join("·"));
  if (typeof f.max_cash === "number") out.push(`현금 ${won(f.max_cash)}`);
  if (typeof f.price_max === "number") out.push(`최저가 ${won(f.price_max)} 이하`);
  if (typeof f.rate_max === "number") out.push(`${f.rate_max}% 이하`);
  if (typeof f.failed_min === "number") out.push(`유찰 ${f.failed_min}회 이상`);
  if (typeof f.days_max === "number") out.push(`${f.days_max}일 안`);
  if (typeof f.area_min === "number" || typeof f.area_max === "number")
    out.push(`${f.area_min ?? ""}~${f.area_max ?? ""}㎡`);
  const ex = f.exclude as string[] | undefined;
  if (ex?.length) out.push(`${ex.length}가지 빼고`);
  return out.join(" · ") || copy.alert.name;
}
