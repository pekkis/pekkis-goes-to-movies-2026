import { createSprinkles, defineProperties } from "@vanilla-extract/sprinkles";
import { breakpoints, space, vars } from "./theme.css.ts";

const layout = defineProperties({
  conditions: {
    mobile: {},
    tablet: { "@media": `screen and (min-width: ${breakpoints.tablet}px)` },
    desktop: { "@media": `screen and (min-width: ${breakpoints.desktop}px)` },
  },
  defaultCondition: "mobile",
  properties: {
    display: ["none", "block", "flex", "grid", "inline-flex"],
    flexDirection: ["row", "column"],
    flexWrap: ["wrap", "nowrap"],
    alignItems: ["stretch", "flex-start", "center", "flex-end", "baseline"],
    justifyContent: ["flex-start", "center", "flex-end", "space-between"],
    gap: space,
    paddingTop: space,
    paddingBottom: space,
    paddingLeft: space,
    paddingRight: space,
    marginTop: space,
    marginBottom: space,
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
