import {
  assignVars,
  createGlobalTheme,
  createThemeContract,
  globalStyle,
} from "@vanilla-extract/css";

/**
 * The design system: every design value the website uses is a token here, and components
 * read `vars`, never literal colors, sizes or fonts. The visual identity (after user
 * testing) will change these values, not the components.
 */
export const vars = createThemeContract({
  color: {
    text: null,
    textMuted: null,
    background: null,
    surface: null,
    border: null,
    accent: null,
    accentText: null,
    link: null,
  },
  space: { none: null, xxs: null, xs: null, sm: null, md: null, lg: null, xl: null },
  font: {
    family: null,
    lineHeight: null,
    size: { xs: null, sm: null, md: null, lg: null, xl: null, xxl: null },
    weight: { regular: null, semibold: null, bold: null, heavy: null },
  },
  border: { width: null, strongWidth: null, focusWidth: null },
  size: {
    /** The page column's maximum width. */
    page: null,
    /** The time column in screening lists. */
    timeColumn: null,
    /** The map's height: most of a phone screen, capped on large screens. */
    map: null,
    /** Poster widths (2:3), in step with POSTER_PX in components/Poster.tsx. */
    posterSm: null,
    posterMd: null,
    posterLg: null,
  },
});

/** Everything except color is the same in light and dark mode. */
const shared = {
  space: {
    none: "0",
    xxs: "0.125rem",
    xs: "0.25rem",
    sm: "0.5rem",
    md: "1rem",
    lg: "1.5rem",
    xl: "2.5rem",
  },
  font: {
    family: 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    lineHeight: "1.5",
    size: {
      xs: "0.75rem",
      sm: "0.875rem",
      md: "1rem",
      lg: "1.125rem",
      xl: "1.25rem",
      xxl: "2rem",
    },
    weight: { regular: "400", semibold: "600", bold: "700", heavy: "800" },
  },
  border: { width: "1px", strongWidth: "3px", focusWidth: "2px" },
  size: {
    page: "56rem",
    timeColumn: "4rem",
    map: "min(70vh, 40rem)",
    posterSm: "4rem",
    posterMd: "9rem",
    posterLg: "14rem",
  },
};

// Grey mockup on purpose: no visual identity before user testing (AGENTS.md, docs/web.md).
// Neutral greys only; meaning comes from layout, text and underlines, not from color.
const light = {
  ...shared,
  color: {
    text: "#1a1a1a",
    textMuted: "#595959",
    background: "#f2f2f2",
    surface: "#ffffff",
    border: "#8c8c8c",
    accent: "#3d3d3d",
    accentText: "#ffffff",
    link: "#1a1a1a",
  },
};

const dark = {
  ...shared,
  color: {
    text: "#e6e6e6",
    textMuted: "#a6a6a6",
    background: "#1a1a1a",
    surface: "#262626",
    border: "#737373",
    accent: "#d0d0d0",
    accentText: "#1a1a1a",
    link: "#e6e6e6",
  },
};

// The OS setting decides; `data-theme` on <html> overrides it.
createGlobalTheme(":root", vars, light);
globalStyle(":root", {
  "@media": { "(prefers-color-scheme: dark)": { vars: assignVars(vars, dark) } },
});
createGlobalTheme(':root[data-theme="light"]', vars, light);
createGlobalTheme(':root[data-theme="dark"]', vars, dark);
