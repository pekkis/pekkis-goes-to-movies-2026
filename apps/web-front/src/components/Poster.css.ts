import { recipe } from "@vanilla-extract/recipes";
import { vars } from "../styles/theme.css.ts";

/** A poster's box: 2:3, a border, and the title in it when there is no image. */
export const poster = recipe({
  base: {
    display: "block",
    aspectRatio: "2 / 3",
    height: "auto",
    objectFit: "cover",
    border: `${vars.border.width} solid ${vars.color.border}`,
    background: vars.color.surface,
  },
  variants: {
    size: {
      sm: { width: vars.size.posterSm },
      md: { width: vars.size.posterMd },
      lg: { width: vars.size.posterLg },
    },
    placeholder: {
      true: {
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: vars.space.xs,
        textAlign: "center",
        fontSize: vars.font.size.xs,
        color: vars.color.textMuted,
        overflow: "hidden",
      },
    },
  },
  defaultVariants: { size: "md" },
});
