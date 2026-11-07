import Link from "next/link";
import { copy } from "@/lib/copy.ko";
import { dday, won } from "@/lib/format";
import { DDay } from "@/components/dday";
import type { PickCard as Pick } from "@/lib/api/items";

const t = copy.home;

// 홈 추천 카드(11/4): 사진을 크게, 아래에 기일·곳·최저가·고른 이유 한 줄. 사진이 없으면 종류 글자 판.
export function PickCard({ c, mode = "pick" }: { c: Pick; mode?: "pick" | "next" }) {
  const line =
    mode === "next"
      ? c.preview
        ? t.nextFixed((c.sale_date ?? "").slice(5).replace("-", "/"), won(c.min_price_krw))
        : c.next_min_krw
          ? c.fail_odds
            ? t.nextOdds(c.fail_odds.of10, won(c.next_min_krw))
            : t.nextFrom(won(c.next_min_krw))
          : null
      : c.reasons[0];
  return (
    <Link href={`/item/${encodeURIComponent(c.item_id)}`} className="pick-card c-inherit">
      <div className="pick-photo">
        {c.photo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={c.photo} alt="" loading="lazy" />
        ) : (
          <span>{c.usage ?? ""}</span>
        )}
        {c.preview && <span className="pick-tag">{t.preview}</span>}
      </div>
      <div className="fs-xs mt-8">
        <DDay d={c.d_day}>
          {dday(c.d_day)} · {c.sale_date?.slice(5).replace("-", "/")}
        </DDay>
      </div>
      <div className="fs-md fw-6 mt-2 ellipsis">
        {c.place} {c.building ?? c.usage}
      </div>
      <div className="fs-base fw-7 mt-2">
        {won(c.min_price_krw)}{" "}
        {c.min_rate != null && <span className="fs-xs fw-5 c-muted">{c.min_rate}%</span>}
      </div>
      {line && <div className="fs-xs c-blue mt-4 pick-why">{line}</div>}
    </Link>
  );
}

export function PickRow({ list, mode }: { list: Pick[]; mode?: "pick" | "next" }) {
  return (
    <div className="pick-row quiet-scroll">
      {list.map((c) => (
        <PickCard key={c.item_id} c={c} mode={mode} />
      ))}
    </div>
  );
}
