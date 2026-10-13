import { globalStyle } from "@vanilla-extract/css";
import { fontFamily, vars } from "./theme.css.ts";

globalStyle("*, *::before, *::after", { boxSizing: "border-box" });
globalStyle("body, h1, h2, h3, p, ul, ol, figure", { margin: 0 });
globalStyle("ul[role='list'], ol[role='list']", { listStyle: "none", padding: 0 });
globalStyle("html", { colorScheme: "light dark", WebkitTextSizeAdjust: "100%" });
globalStyle("body", {
  fontFamily,
  lineHeight: 1.5,
  color: vars.color.text,
  background: vars.color.background,
});
globalStyle("a", { color: vars.color.link });
globalStyle("img", { display: "block", maxWidth: "100%" });
