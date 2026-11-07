import type { FailOdds } from "@/lib/api/items";
import { t } from "@/components/item/shared";

// 「이번에 유찰되면」 아래 유찰 비율 한 줄(11/8 — 휴대폰·PC 상세가 같은 부품).
// 유찰 예상이면 「10건 중 9건 유찰」, 아니면 반대로 「10건 중 9건이 팔림 — 기다리면 놓칠 수 있어요」.
export function OddsLine({ odds, short = false }: { odds?: FailOdds | null; short?: boolean }) {
  if (!odds) return null;
  const sold = 10 - odds.of10;
  const text = short
    ? odds.likely
      ? t.failOddsShort(odds.of10)
      : t.soldOddsShort(sold)
    : odds.likely
      ? t.failOdds(odds.of10, odds.n)
      : t.soldOdds(sold, odds.n);
  return <span className={`sub d-block fs-xs mt-2${short ? " fw-5" : ""}`}>{text}</span>;
}
