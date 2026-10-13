import { style } from "@vanilla-extract/css";
import { vars } from "../../styles/theme.css.ts";

export const popup = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space.xs,
  fontFamily: vars.font.family,
  fontSize: vars.font.size.sm,
});

export const name = style({ fontSize: vars.font.size.md, fontWeight: vars.font.weight.bold });
