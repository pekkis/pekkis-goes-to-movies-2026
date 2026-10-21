import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

/**
 * Draws each journey of docs/design/journey-map.md as one slide-sized image (1920×1080,
 * at twice the resolution): the stages as columns, both feeling curves (today and with
 * us) on one chart, and the thoughts, pain points and opportunities under each stage.
 *
 *   pnpm design:render     # also renders the Mermaid diagrams
 *
 * The data is the document's own tables: edit them, rerun, and the slides follow. Each
 * `## Journey X: "…"` section needs its `**Persona: …**` and `**Goal:**` lines and a table
 * with the rows Stage, Thinks, Pain points, Opportunities, Feeling today, Feeling with us.
 * Black and grey only, told apart by line style and labels, so they print and project well.
 */
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = join(root, "docs/design/journey-map.md");

type Feeling = { score: number; word: string };
type Journey = {
  letter: string;
  title: string;
  persona: string;
  goal: string;
  stages: string[];
  rows: Record<string, string[]>;
  today: Feeling[];
  withUs: Feeling[];
};

/** Markdown in a cell to plain text: no bold, code ticks or links. */
const plain = (text: string) =>
  text
    .replaceAll("**", "")
    .replaceAll("`", "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .trim();

const cells = (line: string) =>
  line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(plain);

const feelings = (row: string[] | undefined, what: string): Feeling[] => {
  if (!row) {
    throw new Error(`No "${what}" row`);
  }
  return row.map((cell) => {
    const m = cell.match(/^([1-5])\s*·\s*(.+)$/);
    if (!m) {
      throw new Error(`"${what}" cell is not "score · word": ${cell}`);
    }
    return { score: Number(m[1]), word: m[2]!.replace(/\s*\(.*\)$/, "") };
  });
};

const parse = (md: string): Journey[] =>
  md
    .split(/^## /m)
    .filter((s) => s.startsWith("Journey "))
    .map((section) => {
      const heading = section.split("\n")[0]!;
      const letter = heading.match(/^Journey (\w+)/)?.[1] ?? "?";
      const title = heading.replace(/^Journey \w+:\s*/, "").replace(/\s*\(.*\)$/, "");
      const persona = plain(section.match(/\*\*Persona: (.+?)\*\*/)?.[1] ?? "");
      const goal = plain(section.match(/\*\*Goal:\*\* (.+)/)?.[1] ?? "");
      const table = section.split("\n").filter((l) => l.startsWith("|") && !/^\|\s*-/.test(l));
      const rows = Object.fromEntries(table.map((l) => cells(l)).map(([k = "", ...v]) => [k, v]));
      const stages = (rows["Stage"] ?? []).map((s) => s.replace(/^\d+\.\s*/, ""));
      return {
        letter,
        title,
        persona,
        goal,
        stages,
        rows,
        today: feelings(rows["Feeling today"], "Feeling today"),
        withUs: feelings(rows["Feeling with us"], "Feeling with us"),
      };
    });

const escape = (text: string) =>
  text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll('"', "&quot;");

// Slide geometry, in CSS pixels.
const W = 1920;
const LABEL = 170;
const PAD = 40;
const COL = (W - 2 * PAD - LABEL) / 7;
const CHART_H = 360;
const y = (score: number) => 30 + ((5 - score) / 4) * (CHART_H - 60);

const curve = (
  points: Feeling[],
  dashed: boolean,
  labelAbove: boolean,
  hide = new Set<number>(),
) => {
  const xy = points.map((p, i) => [LABEL + COL * (i + 0.5), y(p.score)] as const);
  const path = xy.map(([px, py]) => `${px},${py}`).join(" ");
  const marks = xy
    .map(([px, py], i) => {
      const dot = dashed
        ? `<circle cx="${px}" cy="${py}" r="7" fill="#fff" stroke="#777" stroke-width="3"/>`
        : `<circle cx="${px}" cy="${py}" r="7" fill="#111"/>`;
      const ty = labelAbove ? py - 16 : py + 28;
      const word = hide.has(i)
        ? ""
        : `<text x="${px}" y="${ty}" text-anchor="middle" class="${dashed ? "w-today" : "w-us"}">${escape(points[i]!.word)}</text>`;
      return dot + word;
    })
    .join("");
  const line = dashed
    ? `<polyline points="${path}" fill="none" stroke="#777" stroke-width="3" stroke-dasharray="10 8"/>`
    : `<polyline points="${path}" fill="none" stroke="#111" stroke-width="4"/>`;
  return line + marks;
};

const slide = (j: Journey) => {
  const width = W - 2 * PAD;
  // Where both curves meet at the same feeling, the word is printed once (above).
  const same = new Set(
    j.today.flatMap((t, i) =>
      t.score === j.withUs[i]!.score && t.word === j.withUs[i]!.word ? [i] : [],
    ),
  );
  const grid = [1, 2, 3, 4, 5]
    .map(
      (s) =>
        `<line x1="${LABEL}" x2="${width}" y1="${y(s)}" y2="${y(s)}" stroke="#e4e4e4"/>` +
        `<text x="${LABEL - 14}" y="${y(s) + 5}" text-anchor="end" class="axis">${s}</text>`,
    )
    .join("");
  const columns = j.stages
    .map(
      (_, i) =>
        `<line x1="${LABEL + COL * i}" x2="${LABEL + COL * i}" y1="0" y2="${CHART_H}" stroke="#eee"/>`,
    )
    .join("");
  const chart = `<svg width="${width}" height="${CHART_H}" viewBox="0 0 ${width} ${CHART_H}">
    ${columns}${grid}
    <text x="0" y="${y(5) + 5}" class="axis-label">happy</text>
    <text x="0" y="${y(1) + 5}" class="axis-label">frustrated</text>
    ${curve(j.today, true, false, same)}${curve(j.withUs, false, true)}
  </svg>`;
  const row = (name: string, label: string, cls: string) =>
    `<div class="label">${label}</div>` +
    (j.rows[name] ?? []).map((c) => `<div class="cell ${cls}">${escape(c)}</div>`).join("");
  return `<section class="slide">
    <header>
      <h1><span class="letter">Journey ${j.letter}</span> ${escape(j.title)}</h1>
      <p><b>${escape(j.persona)}</b> &nbsp;·&nbsp; Goal: ${escape(j.goal)}</p>
    </header>
    <div class="row stages"><div class="label"></div>${j.stages
      .map((s, i) => `<div class="stage">${i + 1}. ${escape(s)}</div>`)
      .join("")}</div>
    <div class="legend">
      <span><svg width="46" height="14"><line x1="2" x2="44" y1="7" y2="7" stroke="#777" stroke-width="3" stroke-dasharray="10 8"/><circle cx="23" cy="7" r="5" fill="#fff" stroke="#777" stroke-width="3"/></svg> Today</span>
      <span><svg width="46" height="14"><line x1="2" x2="44" y1="7" y2="7" stroke="#111" stroke-width="4"/><circle cx="23" cy="7" r="5" fill="#111"/></svg> With Pekkis goes to movies</span>
    </div>
    ${chart}
    <div class="row">${row("Thinks", "Thinks", "thinks")}</div>
    <div class="row">${row("Pain points", "Pain points", "pain")}</div>
    <div class="row">${row("Opportunities", "With us", "opportunity")}</div>
    <footer>Draft for user testing, ${new Date().toISOString().slice(0, 10)}: assumptions, not yet research.</footer>
  </section>`;
};

const css = `
  * { box-sizing: border-box; margin: 0; }
  body { background: #fff; font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; color: #111; }
  .slide { width: ${W}px; height: 1080px; padding: 36px ${PAD}px; display: flex; flex-direction: column; gap: 10px; }
  header h1 { font-size: 46px; font-weight: 700; }
  header .letter { color: #666; font-weight: 600; margin-right: 8px; }
  header p { font-size: 23px; color: #333; margin-top: 6px; }
  .row { display: grid; grid-template-columns: ${LABEL}px repeat(7, 1fr); }
  .stages { margin-top: 10px; }
  .stage { font-size: 22px; font-weight: 700; padding: 10px 8px; border: 2px solid #111; margin-right: -2px; background: #f2f2f2; text-align: center; }
  .legend { display: flex; gap: 32px; justify-content: flex-end; font-size: 19px; color: #333; }
  .legend span { display: inline-flex; align-items: center; gap: 8px; }
  .label { font-size: 17px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: #555; padding: 10px 12px 0 0; }
  .cell { font-size: 18.5px; line-height: 1.3; padding: 10px 12px; border-left: 1px solid #ddd; }
  .thinks { font-style: italic; color: #333; }
  .pain { background: #f4f4f4; }
  .opportunity { font-weight: 600; }
  .axis { font-size: 14px; fill: #999; }
  .axis-label { font-size: 17px; fill: #777; font-weight: 600; }
  .w-today, .w-us { paint-order: stroke; stroke: #fff; stroke-width: 7px; stroke-linejoin: round; }
  .w-today { font-size: 17px; fill: #666; }
  .w-us { font-size: 19px; fill: #111; font-weight: 700; }
  footer { margin-top: auto; font-size: 16px; color: #888; }
`;

const journeys = parse(await readFile(source, "utf8"));
if (!journeys.length) {
  console.error(`No "## Journey" sections in ${source}`);
  process.exit(1);
}
const browser = await chromium.launch({ channel: "chrome", headless: true });
try {
  const page = await browser.newPage({
    deviceScaleFactor: 2,
    viewport: { width: W, height: 1080 },
  });
  for (const j of journeys) {
    if (j.stages.length !== 7 || j.today.length !== 7 || j.withUs.length !== 7) {
      throw new Error(`Journey ${j.letter}: expected 7 stages and 7 feelings in each row`);
    }
    await page.setContent(`<!doctype html><meta charset="utf-8"><style>${css}</style>${slide(j)}`);
    const file = join(dirname(source), `journey-${j.letter.toLowerCase()}-slide.png`);
    await page.locator(".slide").screenshot({ path: file });
    console.log(`wrote ${file.slice(root.length + 1)}`);
  }
} finally {
  await browser.close();
}
