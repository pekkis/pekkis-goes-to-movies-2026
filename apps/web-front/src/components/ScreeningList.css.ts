import { globalStyle, style } from "@vanilla-extract/css";
import { minWidth } from "../styles/containers.ts";
import { vars } from "../styles/theme.css.ts";

/** The list is its own container: rows adapt to the list's width, wherever it is placed. */
export const list = style({ containerType: "inline-size" });

export const row = style({
  display: "grid",
  gridTemplateColumns: `${vars.size.timeColumn} 1fr`,
  gap: `${vars.space.xs} ${vars.space.md}`,
  padding: `${vars.space.md} 0`,
  borderBottom: `${vars.border.width} solid ${vars.color.border}`,
  "@container": {
    [minWidth("wide")]: {
      gridTemplateColumns: `${vars.size.timeColumn} 1fr auto`,
      alignItems: "center",
    },
  },
});

export const time = style({
  display: "block",
  fontVariantNumeric: "tabular-nums",
  fontWeight: vars.font.weight.bold,
  fontSize: vars.font.size.lg,
});

/** "alkanut" / "alkaa 25 min päästä" under the time. */
export const status = style({
  display: "block",
  fontSize: vars.font.size.xs,
  fontWeight: vars.font.weight.bold,
});

// States in grey only: started is muted, soon gets a strong left edge; the label says which.
globalStyle(`${row}[data-state="started"]`, { color: vars.color.textMuted });
globalStyle(`${row}[data-state="started"] a`, { color: vars.color.textMuted });
globalStyle(`${row}[data-state="soon"]`, {
  borderLeft: `${vars.border.strongWidth} solid ${vars.color.accent}`,
  paddingLeft: vars.space.sm,
});

export const title = style({ fontWeight: vars.font.weight.semibold });

export const meta = style({ color: vars.color.textMuted, fontSize: vars.font.size.sm });

export const badge = style({
  display: "inline-block",
  marginLeft: vars.space.sm,
  padding: `0 ${vars.space.xs}`,
  border: `${vars.border.width} solid ${vars.color.border}`,
  fontSize: vars.font.size.xs,
  color: vars.color.textMuted,
});

export const tickets = style({
  gridColumn: "2",
  justifySelf: "start",
  "@container": { [minWidth("wide")]: { gridColumn: "3" } },
});
