import { globalStyle, style } from "@vanilla-extract/css";
import { space, vars } from "../../styles/theme.css.ts";

export const map = style({
  height: "min(70vh, 40rem)",
  marginBottom: space.lg,
  borderRadius: "0.5rem",
  border: `1px solid ${vars.color.border}`,
  overflow: "hidden",
});

// MapLibre's popup in our theme tokens, so it follows light and dark mode.
globalStyle(`${map} .maplibregl-popup-content`, {
  background: vars.color.surface,
  color: vars.color.text,
  padding: `${space.sm} ${space.md}`,
  borderRadius: "0.5rem",
  boxShadow: "0 4px 16px rgb(0 0 0 / 0.25)",
});
for (const side of ["top", "bottom", "left", "right"] as const) {
  const edge = { top: "Bottom", bottom: "Top", left: "Right", right: "Left" }[side];
  globalStyle(`${map} .maplibregl-popup-anchor-${side} .maplibregl-popup-tip`, {
    [`border${edge}Color`]: vars.color.surface,
  });
}
globalStyle(`${map} .maplibregl-popup-close-button`, {
  color: vars.color.textMuted,
  fontSize: "1.25rem",
  padding: `0 ${space.xs}`,
});
