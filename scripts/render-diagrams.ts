import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

/**
 * Renders the Mermaid diagrams of a design document to PNG images for slides:
 *
 *   pnpm design:render                          # docs/design/journey-map.md
 *   pnpm design:render docs/design/other.md
 *
 * Each ```mermaid block becomes `{document}-{n}.png` next to the document, at twice the
 * resolution. Each block may start with `%% image: name` to name its file instead. Mermaid
 * comes from node_modules (no network), and Playwright drives the installed Chrome, like
 * Finnkino's token step.
 */
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = join(root, process.argv[2] ?? "docs/design/journey-map.md");
const mermaidJs = createRequire(import.meta.url).resolve("mermaid/dist/mermaid.min.js");

const blocks = [...(await readFile(source, "utf8")).matchAll(/```mermaid\n([\s\S]*?)```/g)].map(
  (m) => m[1] ?? "",
);
if (!blocks.length) {
  console.error(`No mermaid blocks in ${source}`);
  process.exit(1);
}
const stem = basename(source, ".md");
const nameOf = (block: string, i: number) =>
  block.match(/^%% image: ([a-z0-9-]+)$/m)?.[1] ?? `${stem}-${i + 1}`;

const escape = (text: string) => text.replaceAll("&", "&amp;").replaceAll("<", "&lt;");
const html = `<!doctype html><meta charset="utf-8"><body style="margin:0;background:#fff">${blocks
  .map(
    (b, i) =>
      `<div id="d${i}" style="display:inline-block;padding:16px"><pre class="mermaid">${escape(b)}</pre></div><br>`,
  )
  .join("")}</body>`;

const browser = await chromium.launch({ channel: "chrome", headless: true });
try {
  const page = await browser.newPage({
    deviceScaleFactor: 2,
    viewport: { width: 1800, height: 1000 },
  });
  await page.setContent(html);
  await page.addScriptTag({ path: mermaidJs });
  const problem = await page.evaluate(async () => {
    const { mermaid } = window as unknown as {
      mermaid: { initialize: (c: object) => void; run: () => Promise<void> };
    };
    mermaid.initialize({ startOnLoad: false, theme: "neutral", journey: { useMaxWidth: false } });
    try {
      await mermaid.run();
      return null;
    } catch (error) {
      return String(error);
    }
  });
  if (problem) {
    throw new Error(`Mermaid failed: ${problem}`);
  }
  for (const [i, block] of blocks.entries()) {
    const box = page.locator(`#d${i}`);
    if (!(await box.locator("svg").count())) {
      throw new Error(`Diagram ${i + 1} did not render`);
    }
    const file = join(dirname(source), `${nameOf(block, i)}.png`);
    await box.screenshot({ path: file });
    console.log(`wrote ${file.slice(root.length + 1)}`);
  }
} finally {
  await browser.close();
}
