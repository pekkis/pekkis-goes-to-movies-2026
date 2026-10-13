import { recipe, type RecipeVariants } from "@vanilla-extract/recipes";
import { vars } from "../theme.css.ts";

/** The pattern for components: a base style plus named variants. */
export const button = recipe({
  base: {
    display: "inline-flex",
    alignItems: "center",
    gap: vars.space.xs,
    border: `${vars.border.width} solid transparent`,
    font: "inherit",
    cursor: "pointer",
    textDecoration: "none",
    ":focus-visible": {
      outline: `${vars.border.focusWidth} solid ${vars.color.accent}`,
      outlineOffset: vars.border.focusWidth,
    },
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
      sm: { padding: `${vars.space.xs} ${vars.space.sm}`, fontSize: vars.font.size.sm },
      md: { padding: `${vars.space.sm} ${vars.space.md}` },
    },
  },
  defaultVariants: { tone: "primary", size: "md" },
});

export type ButtonVariants = RecipeVariants<typeof button>;
