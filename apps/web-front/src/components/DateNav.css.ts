import { style } from "@vanilla-extract/css";
import { vars } from "../styles/theme.css.ts";

export const nav = style({
  display: "flex",
  flexWrap: "wrap",
  alignItems: "flex-end",
  gap: vars.space.md,
  marginBottom: vars.space.md,
});

export const form = style({ display: "flex", alignItems: "flex-end", gap: vars.space.sm });

export const label = style({
  display: "block",
  fontSize: vars.font.size.sm,
  color: vars.color.textMuted,
});

export const field = style({
  padding: `${vars.space.xs} ${vars.space.sm}`,
  border: `${vars.border.width} solid ${vars.color.border}`,
  background: vars.color.surface,
  color: vars.color.text,
  font: "inherit",
});
