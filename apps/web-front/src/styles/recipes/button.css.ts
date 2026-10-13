import { recipe, type RecipeVariants } from "@vanilla-extract/recipes";
import { space, vars } from "../theme.css.ts";

/** The pattern for components: a base style plus named variants. */
export const button = recipe({
  base: {
    display: "inline-flex",
    alignItems: "center",
    gap: space.xs,
    border: "1px solid transparent",
    borderRadius: "0.375rem",
    font: "inherit",
    cursor: "pointer",
    textDecoration: "none",
    ":focus-visible": { outline: `2px solid ${vars.color.accent}`, outlineOffset: "2px" },
  },
  variants: {
    tone: {
      primary: { background: vars.color.accent, color: vars.color.accentText },
      ghost: {
        background: "transparent",
        color: vars.color.text,
        borderColor: vars.color.border,
      },
    },
    size: {
      sm: { padding: `${space.xs} ${space.sm}`, fontSize: "0.875rem" },
      md: { padding: `${space.sm} ${space.md}` },
    },
  },
  defaultVariants: { tone: "primary", size: "md" },
});

export type ButtonVariants = RecipeVariants<typeof button>;
