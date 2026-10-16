import { styleText } from "node:util";

/**
 * Colours for terminal reports. Only the basic ANSI colours and bold: terminal themes
 * adapt those to dark and light backgrounds alike. Meaning is never in the colour alone;
 * the words stay the same without it.
 */
export type Paint = (format: Parameters<typeof styleText>[0], text: string) => string;

/**
 * Paints for one stream: colour only on a terminal, and never under NO_COLOR (styleText's
 * own checks; FORCE_COLOR forces it).
 */
export const paintFor =
  (stream: NodeJS.WriteStream): Paint =>
  (format, text) =>
    styleText(format, text, { stream });

/** No colour (tests, files). */
export const plain: Paint = (_format, text) => text;
