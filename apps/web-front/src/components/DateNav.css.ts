import { style } from "@vanilla-extract/css";
import { space, vars } from "../styles/theme.css.ts";

export const nav = style({
  display: "flex",
  flexWrap: "wrap",
  alignItems: "flex-end",
  gap: space.md,
  marginBottom: space.md,
});

export const form = style({ display: "flex", alignItems: "flex-end", gap: space.sm });

export const label = style({ display: "block", fontSize: "0.875rem", color: vars.color.textMuted });

export const field = style({
  padding: `${space.xs} ${space.sm}`,
  border: `1px solid ${vars.color.border}`,
  borderRadius: "0.375rem",
  background: vars.color.surface,
  color: vars.color.text,
  font: "inherit",
});
