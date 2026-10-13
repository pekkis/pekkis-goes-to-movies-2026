import { style } from "@vanilla-extract/css";
import { space, vars } from "../styles/theme.css.ts";

export const page = style({ maxWidth: "56rem", margin: "0 auto", padding: `0 ${space.md}` });

export const brand = style({ fontWeight: 800, textDecoration: "none", color: vars.color.text });

export const footer = style({
  marginTop: space.xl,
  padding: `${space.lg} 0`,
  borderTop: `1px solid ${vars.color.border}`,
  color: vars.color.textMuted,
  fontSize: "0.8125rem",
});
