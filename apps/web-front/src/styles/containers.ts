/**
 * Container widths where layouts change, mobile first: below `wide` is the phone layout.
 * Part of the design system (with theme.css.ts), but a plain module: .css.ts files may only
 * export data, and CSS can't use custom properties in container conditions anyway.
 * Use these only in `@container (min-width: …)` queries, never in viewport media queries.
 */
export const containerWidths = { wide: "40rem", widest: "64rem" } as const;

/** `@container` condition for `min-width` at one of the container widths. */
export const minWidth = (width: keyof typeof containerWidths): string =>
  `(min-width: ${containerWidths[width]})`;
