import { globalStyle, style } from "@vanilla-extract/css";
import { vars } from "../styles/theme.css.ts";

export const film = style({
  padding: `${vars.space.md} 0`,
  borderBottom: `${vars.border.width} solid ${vars.color.border}`,
});

export const title = style({ fontSize: vars.font.size.lg, fontWeight: vars.font.weight.bold });

export const facts = style({
  color: vars.color.textMuted,
  fontSize: vars.font.size.sm,
  marginBottom: vars.space.sm,
});

export const shows = style({ display: "flex", flexWrap: "wrap", gap: vars.space.sm });

export const show = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space.xxs,
  fontSize: vars.font.size.xs,
  color: vars.color.textMuted,
});

export const time = style({
  fontVariantNumeric: "tabular-nums",
  fontWeight: vars.font.weight.bold,
});

/** The time box that is the ticket link. */
export const ticket = style({});

/** "alkanut" / "alkaa 25 min päästä" under the time. */
export const status = style({
  fontWeight: vars.font.weight.bold,
});

// States in grey only: started is muted, soon gets a strong border; the label says which.
globalStyle(`${show}[data-state="started"] time`, { fontWeight: vars.font.weight.regular });
globalStyle(`${show}[data-state="soon"] ${ticket}`, {
  borderWidth: vars.border.strongWidth,
  borderColor: vars.color.accent,
});
