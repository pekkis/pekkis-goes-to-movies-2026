import { style } from "@vanilla-extract/css";
import { space } from "../../styles/theme.css.ts";

export const popup = style({
  display: "flex",
  flexDirection: "column",
  gap: space.xs,
  fontFamily: "inherit",
  fontSize: "0.875rem",
});

export const name = style({ fontSize: "1rem", fontWeight: 700 });
