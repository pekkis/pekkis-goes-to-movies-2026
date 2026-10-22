import { ScreeningTag, TAG_GROUPS } from "@pgtm/model";
import { addDays } from "@pgtm/model/time";
import { kindScreenings, listSeries, type Api, type Screening, type Series } from "./api.ts";
import { TAG_NAMES } from "./text.ts";

const nameOrder = new Intl.Collator("fi", { sensitivity: "base", numeric: true });

/**
 * The special screenings page (/fi/erikoisnaytokset): pick kinds of screening, tags
 * (classics, domestic films, baby screenings) and series (knitting screenings, a director
 * retrospective, Kahvikino), and see their screenings in the coming weeks. A plain GET form,
 * so the address can be shared: `?sarja=neulekino&tunniste=baby`.
 */

/** How far ahead the page looks: four weeks. */
export const KIND_DAYS = 28;
/** Screenings shown at most: a broad tag ("domestic") has thousands in four weeks. */
export const MAX_SHOWN = 300;
/** At most this many choices in one address, of each kind. */
const MAX_CHOICES = 20;
const SERIES_ID = /^[a-z0-9-]+(?:\/[a-z0-9-]+)?$/;

export type KindsParams = { tags: ScreeningTag[]; series: string[] };

/** The address's choices: known tags only, well-formed series ids, each once. */
export const parseKindsParams = (params: URLSearchParams): KindsParams => {
  const tags = [...new Set(params.getAll("tunniste"))].filter(
    (t): t is ScreeningTag => ScreeningTag.safeParse(t).success,
  );
  const series = [...new Set(params.getAll("sarja"))].filter(
    (id) => id.length <= 200 && SERIES_ID.test(id),
  );
  return { tags: tags.slice(0, MAX_CHOICES), series: series.slice(0, MAX_CHOICES) };
};

/** Every tag, in the model's groups (occasion, origin, audience, …). */
export const TAG_CHOICES = Object.entries(TAG_GROUPS).map(([group, tags]) => ({
  group: group as keyof typeof TAG_GROUPS,
  tags: [...tags] as ScreeningTag[],
}));

export type KindsPage = {
  params: KindsParams;
  from: string;
  to: string;
  /** Series with screenings in the period, plus any chosen one that has none now; by name. */
  series: Series[];
  /** The chosen tags' and series' names, for the summary above the results. */
  chosenNames: string[];
  /** "start": nothing chosen yet. */
  state: "start" | "results";
  /** The chosen kinds' screenings, by programme day, in time order. */
  days: { date: string; screenings: Screening[] }[];
  /** More screenings than MAX_SHOWN: only the first are shown. */
  more: boolean;
};

export const loadKindsPage = async (
  api: Api,
  query: URLSearchParams,
  today: string,
): Promise<KindsPage> => {
  const params = parseKindsParams(query);
  const from = today;
  const to = addDays(today, KIND_DAYS - 1);
  const chosen = params.tags.length > 0 || params.series.length > 0;
  const [listed, shown] = await Promise.all([
    listSeries(api, from, to),
    chosen
      ? kindScreenings(api, { from, to, ...params, limit: MAX_SHOWN })
      : Promise.resolve({ items: [], more: false }),
  ]);
  const screenings = shown.items;
  // A shared address may name a series with nothing on now: keep it, so it stays checked.
  const missing = params.series
    .filter((id) => !listed.some((s) => s.id === id))
    .map((id) => ({ id, name: id, kind: "strand", screenings: 0, firstDay: "" }));
  const days = Object.entries(Object.groupBy(screenings, (s) => s.businessDate))
    .map(([date, shows]) => ({ date, screenings: shows ?? [] }))
    .toSorted((a, b) => a.date.localeCompare(b.date));
  const series = [...listed, ...missing].toSorted((a, b) => nameOrder.compare(a.name, b.name));
  return {
    params,
    from,
    to,
    series,
    chosenNames: [
      ...params.tags.map((t) => TAG_NAMES[t]),
      ...params.series.map((id) => series.find((s) => s.id === id)?.name ?? id),
    ],
    state: chosen ? "results" : "start",
    days,
    more: shown.more,
  };
};
