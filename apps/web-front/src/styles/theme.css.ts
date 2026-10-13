import {
  assignVars,
  createGlobalTheme,
  createThemeContract,
  globalStyle,
} from "@vanilla-extract/css";

/** Design tokens. Components read `vars`; themes fill them in. */
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
});

const light = {
  color: {
    text: "#1b1b1f",
    textMuted: "#5d5d66",
    background: "#fafaf7",
    surface: "#ffffff",
    border: "#dcdcd4",
    accent: "#b3261e",
    accentText: "#ffffff",
    link: "#8a1c16",
  },
};

const dark = {
  color: {
    text: "#ececf1",
    textMuted: "#a5a5b0",
    background: "#141417",
    surface: "#1e1e23",
    border: "#34343c",
    accent: "#ff8a80",
    accentText: "#141417",
    link: "#ffb4ab",
  },
};

// The OS setting decides; `data-theme` on <html> overrides it.
createGlobalTheme(":root", vars, light);
globalStyle(":root", {
  "@media": { "(prefers-color-scheme: dark)": { vars: assignVars(vars, dark) } },
});
createGlobalTheme(':root[data-theme="light"]', vars, light);
createGlobalTheme(':root[data-theme="dark"]', vars, dark);

/** Spacing scale, in rem. */
export const space = {
  none: "0",
  xs: "0.25rem",
  sm: "0.5rem",
  md: "1rem",
  lg: "1.5rem",
  xl: "2.5rem",
} as const;

export const breakpoints = { tablet: 640, desktop: 1024 } as const;

export const fontFamily =
  'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
