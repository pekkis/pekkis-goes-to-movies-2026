import { style } from "@vanilla-extract/css";
import { vars } from "../styles/theme.css.ts";

/** "Näytä alkaneet (n)": the collapsed started shows above the rest of the day. */
export const started = style({ marginBottom: vars.space.md });
