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

// ── 스타일 정리 지키기(11/23 대표님 「새로 더하기 전에 있는 것부터」) ──
// ① !important 와 토큰 밖 숫자(글자 크기 px · 둥글기 px · 색 #)가 아래 기준보다 늘면 멈춤 — 값은 tokens.css 토큰으로.
//    줄었으면 기준 숫자를 그만큼 낮춰 적어 둠(다시 늘지 않게).
// ② CSS 에만 있고 화면 코드 어디에도 안 나오는 클래스 이름이 생기면 멈춤(안 쓰는 규칙은 지움).
const STYLE_MAX = { important: 196, 글자크기px: 103, 둥글기px: 156, 색: 35 };
const DYNAMIC = ["k-", "dd-", "logo-"]; // 화면이 `k-${…}` 처럼 이어 붙여 쓰는 이름
const cssFiles = [];
(function css(d) {
  for (const n of readdirSync(d)) {
    const p = join(d, n);
    if (statSync(p).isDirectory()) css(p);
    else if (n.endsWith(".css")) cssFiles.push(p);
  }
})(join(web, "app"));
const count = { important: 0, 글자크기px: 0, 둥글기px: 0, 색: 0 };
const cssClasses = new Set();
for (const p of cssFiles) {
  const t = readFileSync(p, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  count.important += (t.match(/!important/g) ?? []).length;
  if (!p.endsWith("tokens.css")) {
    count.글자크기px += (t.match(/font-size:\s*[\d.]+px/g) ?? []).length;
    count.둥글기px += (t.match(/border-radius:\s*[\d.]+px/g) ?? []).length;
    count.색 += (t.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).length;
  }
  for (const sel of t.match(/[^{}]+(?=\{)/g) ?? [])
    if (!sel.trim().startsWith("@"))
      for (const m of sel.matchAll(/\.([a-zA-Z][\w-]*)/g)) cssClasses.add(m[1]);
}
for (const k of Object.keys(STYLE_MAX))
  if (count[k] > STYLE_MAX[k])
    bad.push(
      `스타일 ${k} ${count[k]}곳(기준 ${STYLE_MAX[k]}) — 숫자 대신 tokens.css 토큰을, !important 대신 덮는 규칙을 고치세요`,
    );
let code = "";
(function src(d) {
  for (const n of readdirSync(d)) {
    if (n === "node_modules" || n.startsWith(".")) continue;
    const p = join(d, n);
    if (statSync(p).isDirectory()) src(p);
    else if (/\.(ts|tsx)$/.test(n)) code += readFileSync(p, "utf8") + "\n";
  }
})(web);
const words = new Set(code.match(/[A-Za-z][\w-]*/g) ?? []);
const unused = [...cssClasses].filter(
  (c) => !words.has(c) && !DYNAMIC.some((x) => c.startsWith(x)),
);
if (unused.length)
  bad.push(`안 쓰는 스타일 이름 ${unused.length}개(지우세요): ${unused.join(", ")}`);
const lower = Object.keys(STYLE_MAX).filter((k) => count[k] < STYLE_MAX[k]);
if (lower.length)
  console.log(
    `스타일 기준을 낮춰 적어 주세요: ${lower.map((k) => `${k} ${STYLE_MAX[k]} → ${count[k]}`).join(" · ")}`,
  );

if (bad.length) {
  console.log("금지 꼴:\n" + bad.join("\n"));
  process.exit(1);
}
console.log("금지 꼴 없음");
