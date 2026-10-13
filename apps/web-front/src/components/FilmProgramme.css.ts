import { style } from "@vanilla-extract/css";
import { space, vars } from "../styles/theme.css.ts";

export const film = style({
  padding: `${space.md} 0`,
  borderBottom: `1px solid ${vars.color.border}`,
});

export const title = style({ fontSize: "1.125rem", fontWeight: 700 });

export const facts = style({
  color: vars.color.textMuted,
  fontSize: "0.875rem",
  marginBottom: space.sm,
});

export const shows = style({ display: "flex", flexWrap: "wrap", gap: space.sm });

export const show = style({
  display: "flex",
  flexDirection: "column",
  gap: "0.125rem",
  fontSize: "0.8125rem",
  color: vars.color.textMuted,
});

export const time = style({ fontVariantNumeric: "tabular-nums", fontWeight: 700 });
