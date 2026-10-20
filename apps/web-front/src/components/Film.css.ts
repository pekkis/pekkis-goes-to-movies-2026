import { style } from "@vanilla-extract/css";
import { minWidth } from "../styles/containers.ts";
import { vars } from "../styles/theme.css.ts";

/** The film page's head: poster above the text on a phone, beside it when there is room. */
export const headContainer = style({ containerType: "inline-size", marginBottom: vars.space.lg });

export const head = style({
  display: "grid",
  gap: vars.space.md,
  "@container": {
    [minWidth("wide")]: { gridTemplateColumns: "auto 1fr", alignItems: "start" },
  },
});

export const facts = style({ color: vars.color.textMuted, marginBottom: vars.space.sm });

export const overview = style({ marginBottom: vars.space.sm, maxWidth: "40em" });

export const links = style({ display: "flex", flexWrap: "wrap", gap: vars.space.md });

/** The day links: a row of boxes, the chosen day in bold. */
export const days = style({
  display: "flex",
  flexWrap: "wrap",
  gap: vars.space.sm,
  marginBottom: vars.space.md,
});

export const day = style({
  padding: `${vars.space.xs} ${vars.space.sm}`,
  border: `${vars.border.width} solid ${vars.color.border}`,
  selectors: {
    '&[aria-current="date"]': {
      fontWeight: vars.font.weight.bold,
      borderWidth: vars.border.strongWidth,
    },
  },
});

export const empty = style({ color: vars.color.textMuted });

/** A grid of poster cards, as many columns as fit. */
export const gridContainer = style({ containerType: "inline-size", marginBottom: vars.space.lg });

export const grid = style({
  display: "grid",
  gridTemplateColumns: `repeat(auto-fill, minmax(${vars.size.posterMd}, 1fr))`,
  gap: vars.space.md,
});

export const card = style({ display: "grid", gap: vars.space.xs, alignContent: "start" });

export const cardTitle = style({ fontWeight: vars.font.weight.semibold });

export const cardMeta = style({ fontSize: vars.font.size.sm, color: vars.color.textMuted });
