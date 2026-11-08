// 금지 꼴 찾기(11/8, project-standard 3-4·9장) — 배포 2단계에서 몇 초 안에.
// 브라우저 기본 기능을 덮어쓰면 그것을 쓰는 모든 곳이 조용히 망가지고(scrollTo 사고),
// 정규식 lookbehind는 옛 아이폰 사파리에서 화면 전체가 멈춤. 찾으면 배포를 멈춤.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const web = fileURLToPath(new URL("..", import.meta.url));
const RULES = [
  [/\(\?<[=!]/, "정규식 lookbehind — 옛 아이폰 사파리에서 멈춤"],
  [
    /\b(window|document|history|navigator|Element|HTMLElement)\.(scrollTo|scrollBy|scrollIntoView|fetch|pushState|replaceState|alert|confirm|open)\s*=[^=]/,
    "브라우저 기본 기능 덮어쓰기",
  ],
  [/\b(window\.)?fetch\s*=\s*(async\s*)?\(/, "fetch 덮어쓰기"],
  [/\.prototype\.\w+\s*=[^=]/, "기본 기능(prototype) 덮어쓰기"],
  [/\b(sk-[A-Za-z0-9]{20,}|service_role)\b/, "비밀 키 꼴"],
];
const bad = [];
function walk(d) {
  for (const n of readdirSync(d)) {
    if (n === "node_modules" || n.startsWith(".")) continue;
    const p = join(d, n);
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.(ts|tsx|js|mjs)$/.test(n) && !n.endsWith(".test.ts") && n !== "banned.mjs") {
      readFileSync(p, "utf8")
        .split("\n")
        .forEach((line, i) => {
          for (const [re, why] of RULES)
            if (re.test(line)) bad.push(`${relative(web, p)}:${i + 1}  ${why}`);
        });
    }
  }
}
for (const d of ["app", "components", "lib", "public"]) walk(join(web, d));
if (bad.length) {
  console.log("금지 꼴:\n" + bad.join("\n"));
  process.exit(1);
}
console.log("금지 꼴 없음");
