import { style } from "@vanilla-extract/css";
import { vars } from "../styles/theme.css.ts";

export const page = style({
  maxWidth: vars.size.page,
  margin: "0 auto",
  padding: `0 ${vars.space.md}`,
});

/** The page's content area is the container that responsive sprinkles query. */
export const main = style({ containerType: "inline-size" });

export const brand = style({
  fontWeight: vars.font.weight.heavy,
  textDecoration: "none",
  color: vars.color.text,
});

export const footer = style({
  marginTop: vars.space.xl,
  padding: `${vars.space.lg} 0`,
  borderTop: `${vars.border.width} solid ${vars.color.border}`,
  color: vars.color.textMuted,
  fontSize: vars.font.size.sm,
});
