import { style } from "@vanilla-extract/css";
import { space, vars } from "../styles/theme.css.ts";

export const form = style({ display: "flex", alignItems: "flex-end", gap: space.sm });

export const label = style({ display: "block", fontSize: "0.875rem", color: vars.color.textMuted });

export const field = style({
  display: "inline-flex",
  alignItems: "center",
  gap: space.xs,
  padding: `${space.xs} ${space.sm}`,
  border: `1px solid ${vars.color.border}`,
  borderRadius: "0.375rem",
  background: vars.color.surface,
  color: vars.color.text,
  font: "inherit",
});

export const segment = style({
  fontVariantNumeric: "tabular-nums",
  selectors: { "&[data-focused]": { background: vars.color.accent, color: vars.color.accentText } },
});

export const popover = style({
  padding: space.md,
  border: `1px solid ${vars.color.border}`,
  borderRadius: "0.5rem",
  background: vars.color.surface,
  color: vars.color.text,
  boxShadow: "0 8px 24px rgb(0 0 0 / 0.2)",
});

export const calendarHeader = style({
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: space.sm,
  marginBottom: space.sm,
});

export const cell = style({
  display: "grid",
  placeItems: "center",
  width: "2.25rem",
  height: "2.25rem",
  borderRadius: "50%",
  cursor: "pointer",
  selectors: {
    "&[data-outside-month]": { display: "none" },
    "&[data-selected]": { background: vars.color.accent, color: vars.color.accentText },
    "&[data-focus-visible]": { outline: `2px solid ${vars.color.accent}` },
  },
});
