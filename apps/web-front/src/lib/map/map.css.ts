import { globalStyle, style } from "@vanilla-extract/css";
import { vars } from "../../styles/theme.css.ts";

export const map = style({
  height: vars.size.map,
  marginBottom: vars.space.lg,
  border: `${vars.border.width} solid ${vars.color.border}`,
  overflow: "hidden",
});

// MapLibre's popup in our theme tokens, so it follows light and dark mode.
globalStyle(`${map} .maplibregl-popup-content`, {
  background: vars.color.surface,
  color: vars.color.text,
  padding: `${vars.space.sm} ${vars.space.md}`,
  border: `${vars.border.width} solid ${vars.color.border}`,
});
for (const side of ["top", "bottom", "left", "right"] as const) {
  const edge = { top: "Bottom", bottom: "Top", left: "Right", right: "Left" }[side];
  globalStyle(`${map} .maplibregl-popup-anchor-${side} .maplibregl-popup-tip`, {
    [`border${edge}Color`]: vars.color.border,
  });
}
globalStyle(`${map} .maplibregl-popup-close-button`, {
  color: vars.color.textMuted,
  fontSize: vars.font.size.xl,
  padding: `0 ${vars.space.xs}`,
});
