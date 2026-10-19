import { globalStyle, style } from "@vanilla-extract/css";
import { minWidth } from "../styles/containers.ts";
import { vars } from "../styles/theme.css.ts";

// The search page: grey boxes and borders only (docs/web.md, visual style). A checked
// value is shown by its checkbox and bold text, never by colour.

export const form = style({
  display: "grid",
  gap: vars.space.md,
  padding: vars.space.md,
  marginBottom: vars.space.lg,
  border: `${vars.border.width} solid ${vars.color.border}`,
  background: vars.color.surface,
});

export const fieldset = style({
  display: "grid",
  gap: vars.space.xs,
  border: "none",
  padding: 0,
  margin: 0,
});

export const legend = style({
  padding: 0,
  marginBottom: vars.space.xs,
  fontWeight: vars.font.weight.bold,
});

export const choices = style({
  display: "flex",
  flexWrap: "wrap",
  alignItems: "center",
  gap: vars.space.sm,
});

export const choice = style({
  display: "inline-flex",
  alignItems: "center",
  gap: vars.space.xs,
  padding: `${vars.space.xs} ${vars.space.sm}`,
  border: `${vars.border.width} solid ${vars.color.border}`,
});

export const field = style({
  padding: `${vars.space.xs} ${vars.space.sm}`,
  border: `${vars.border.width} solid ${vars.color.border}`,
  background: vars.color.surface,
  color: vars.color.text,
  font: "inherit",
  maxWidth: "100%",
});

/** Facets and results: stacked on a phone, side by side when the page is wide enough. */
export const layoutContainer = style({ containerType: "inline-size" });

export const layout = style({
  display: "grid",
  gap: vars.space.lg,
  "@container": {
    [minWidth("wide")]: { gridTemplateColumns: "minmax(17rem, 1fr) 2fr", alignItems: "start" },
  },
});

export const facets = style({ display: "grid", gap: vars.space.md, alignContent: "start" });

export const facet = style({
  border: `${vars.border.width} solid ${vars.color.border}`,
  background: vars.color.surface,
  padding: vars.space.sm,
});

export const facetTitle = style({ fontWeight: vars.font.weight.bold, cursor: "pointer" });

export const options = style({
  display: "grid",
  gap: vars.space.xxs,
  marginTop: vars.space.sm,
});

export const option = style({
  display: "grid",
  gridTemplateColumns: "auto 1fr auto",
  alignItems: "baseline",
  gap: vars.space.sm,
  cursor: "pointer",
});

globalStyle(`${option}[data-checked]`, { fontWeight: vars.font.weight.bold });

export const count = style({
  fontVariantNumeric: "tabular-nums",
  fontSize: vars.font.size.sm,
  color: vars.color.textMuted,
});

export const muted = style({
  color: vars.color.textMuted,
  fontSize: vars.font.size.sm,
  fontWeight: vars.font.weight.regular,
  whiteSpace: "nowrap",
});

/** "Siirry näytöksiin": on a phone the facets come first, so the results are a jump away. */
export const skip = style({
  "@container": { [minWidth("wide")]: { display: "none" } },
});

export const results = style({ minWidth: 0 });

export const summary = style({ fontWeight: vars.font.weight.bold, marginBottom: vars.space.sm });

export const dayHeading = style({
  fontSize: vars.font.size.lg,
  marginTop: vars.space.lg,
  paddingBottom: vars.space.xs,
  borderBottom: `${vars.border.strongWidth} solid ${vars.color.border}`,
});

/** A group's members (a provider's venues), indented under the group's own checkbox. */
export const nested = style({
  display: "grid",
  gap: vars.space.xxs,
  marginTop: vars.space.xxs,
  marginBottom: vars.space.xs,
  paddingLeft: vars.space.lg,
  borderLeft: `${vars.border.width} solid ${vars.color.border}`,
});
