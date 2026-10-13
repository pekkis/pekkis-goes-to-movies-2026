import { createSprinkles, defineProperties } from "@vanilla-extract/sprinkles";
import { minWidth } from "./containers.ts";
import { vars } from "./theme.css.ts";

/**
 * Responsive layout, mobile first: the default is the narrow layout, and `wide` / `widest`
 * apply when the nearest container (`main`, or a component's own) is at least that wide.
 * Container queries, not viewport media queries, so a component adapts to the space it gets.
 */
const layout = defineProperties({
  conditions: {
    narrow: {},
    wide: { "@container": minWidth("wide") },
    widest: { "@container": minWidth("widest") },
  },
  defaultCondition: "narrow",
  properties: {
    display: ["none", "block", "flex", "grid", "inline-flex"],
    flexDirection: ["row", "column"],
    flexWrap: ["wrap", "nowrap"],
    alignItems: ["stretch", "flex-start", "center", "flex-end", "baseline"],
    justifyContent: ["flex-start", "center", "flex-end", "space-between"],
    gap: vars.space,
    paddingTop: vars.space,
    paddingBottom: vars.space,
    paddingLeft: vars.space,
    paddingRight: vars.space,
    marginTop: vars.space,
    marginBottom: vars.space,
  },
  shorthands: {
    padding: ["paddingTop", "paddingBottom", "paddingLeft", "paddingRight"],
    paddingX: ["paddingLeft", "paddingRight"],
    paddingY: ["paddingTop", "paddingBottom"],
    marginY: ["marginTop", "marginBottom"],
  },
});

const colors = defineProperties({
  properties: {
    color: vars.color,
    background: vars.color,
  },
});

/** Atomic layout, spacing and color classes on design tokens. */
export const sprinkles = createSprinkles(layout, colors);
export type Sprinkles = Parameters<typeof sprinkles>[0];
