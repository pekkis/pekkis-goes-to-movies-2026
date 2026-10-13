import { style } from "@vanilla-extract/css";
import { breakpoints, space, vars } from "../styles/theme.css.ts";

export const row = style({
  display: "grid",
  gridTemplateColumns: "4rem 1fr",
  gap: `${space.xs} ${space.md}`,
  padding: `${space.md} 0`,
  borderBottom: `1px solid ${vars.color.border}`,
  "@media": {
    [`screen and (min-width: ${breakpoints.tablet}px)`]: {
      gridTemplateColumns: "4rem 1fr auto",
      alignItems: "center",
    },
  },
});

export const time = style({
  fontVariantNumeric: "tabular-nums",
  fontWeight: 700,
  fontSize: "1.125rem",
});

export const title = style({ fontWeight: 600 });

export const meta = style({ color: vars.color.textMuted, fontSize: "0.875rem" });

export const badge = style({
  display: "inline-block",
  marginLeft: space.sm,
  padding: `0 ${space.xs}`,
  borderRadius: "0.25rem",
  border: `1px solid ${vars.color.border}`,
  fontSize: "0.75rem",
  color: vars.color.textMuted,
});

export const tickets = style({
  gridColumn: "2",
  justifySelf: "start",
  "@media": {
    [`screen and (min-width: ${breakpoints.tablet}px)`]: { gridColumn: "3" },
  },
});
