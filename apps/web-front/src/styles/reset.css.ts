import { globalStyle } from "@vanilla-extract/css";
import { vars } from "./theme.css.ts";

globalStyle("*, *::before, *::after", { boxSizing: "border-box" });
globalStyle("body, h1, h2, h3, p, ul, ol, dl, dd, figure", { margin: 0 });
globalStyle("ul[role='list'], ol[role='list']", { listStyle: "none", padding: 0 });
globalStyle("html", { colorScheme: "light dark", WebkitTextSizeAdjust: "100%" });
globalStyle("body", {
  fontFamily: vars.font.family,
  fontSize: vars.font.size.md,
  lineHeight: vars.font.lineHeight,
  color: vars.color.text,
  background: vars.color.background,
});
globalStyle("h1", { fontSize: vars.font.size.xxl, lineHeight: 1.2 });
globalStyle("h2", { fontSize: vars.font.size.xl, lineHeight: 1.3 });
globalStyle("a", { color: vars.color.link });
globalStyle("img", { display: "block", maxWidth: "100%" });
