import type { Screening } from "../lib/api.ts";
import { FilmProgramme } from "./FilmProgramme.tsx";
import { NowProvider } from "./now.tsx";

/**
 * The venue page's day, as an island (`client:idle`): rendered on the server at the
 * server's time, then kept current in the browser.
 */
export const VenueProgramme = ({ screenings, now }: { screenings: Screening[]; now: string }) => (
  <NowProvider initial={now}>
    <FilmProgramme screenings={screenings} />
  </NowProvider>
);
