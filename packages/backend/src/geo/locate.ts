import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { promisify } from "node:util";
import { REPO_ROOT } from "../lib/paths.ts";

/** Where the showtimes CLI searches from: a point plus how it was found, for the user. */
export type Located = { lat: number; lon: number; label: string; approximate: boolean };

const userAgent = (contact?: string) =>
  `pekkis-goes-to-movies/0.1 (showtimes CLI${contact ? `; ${contact}` : ""})`;

const isPoint = (lat: unknown, lon: unknown): boolean =>
  typeof lat === "number" &&
  typeof lon === "number" &&
  Math.abs(lat) <= 90 &&
  Math.abs(lon) <= 180 &&
  !(lat === 0 && lon === 0);

// --- CoreLocationCLI (macOS: Wi-Fi positioning, like Maps) -----------------------------

/** Pure: CoreLocationCLI `--json` output -> point. */
export const parseCoreLocation = (stdout: string): Located | undefined => {
  try {
    const d = JSON.parse(stdout) as Record<string, unknown>;
    const lat = Number(d["latitude"]);
    const lon = Number(d["longitude"]);
    if (!isPoint(lat, lon)) return undefined;
    const accuracy = Number(d["h_accuracy"] ?? d["horizontalAccuracy"]);
    return {
      lat,
      lon,
      label: `this Mac (CoreLocation${Number.isFinite(accuracy) ? `, ±${Math.round(accuracy)} m` : ""})`,
      approximate: false,
    };
  } catch {
    return undefined;
  }
};

/** Undefined when CoreLocationCLI is not installed; throws when it fails (e.g. denied). */
export const fromCoreLocation = async (): Promise<Located | undefined> => {
  try {
    const { stdout } = await promisify(execFile)("CoreLocationCLI", ["--json"], {
      timeout: 20_000,
    });
    const located = parseCoreLocation(stdout);
    if (!located) throw new Error(`CoreLocationCLI gave no position: ${stdout.trim()}`);
    return located;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
    throw new Error(
      `CoreLocationCLI failed (is Location Services allowed for your terminal?): ${(error as Error).message}`,
    );
  }
};

// --- IP geolocation (any machine; city-level at best) ----------------------------------

/** Pure: ipinfo.io `/json` -> point ("loc": "60.1695,24.9354"). */
export const parseIpinfo = (body: unknown): Located | undefined => {
  if (!body || typeof body !== "object") return undefined;
  const d = body as Record<string, unknown>;
  const [lat, lon] = String(d["loc"] ?? "")
    .split(",")
    .map(Number);
  if (!isPoint(lat, lon)) return undefined;
  const place = [d["city"], d["region"]].filter((x) => typeof x === "string" && x).join(", ");
  return {
    lat: lat!,
    lon: lon!,
    label: `your IP address (ipinfo.io${place ? `: ${place}` : ""})`,
    approximate: true,
  };
};

/** Sends the machine's public IP address to ipinfo.io. */
export const fromIp = async (contact?: string): Promise<Located> => {
  const res = await fetch("https://ipinfo.io/json", {
    headers: { accept: "application/json", "user-agent": userAgent(contact) },
    signal: AbortSignal.timeout(10_000),
  });
  if (!res.ok) throw new Error(`ipinfo.io answered ${res.status}`);
  const located = parseIpinfo(await res.json());
  if (!located) throw new Error("ipinfo.io gave no position");
  return located;
};

// --- Address geocoding (OpenStreetMap Nominatim) ---------------------------------------

/** Pure: Nominatim jsonv2 search results -> the best match. */
export const parseNominatim = (body: unknown): Located | undefined => {
  if (!Array.isArray(body) || body.length === 0) return undefined;
  const top = body[0] as Record<string, unknown>;
  const lat = Number(top["lat"]);
  const lon = Number(top["lon"]);
  if (!isPoint(lat, lon)) return undefined;
  return {
    lat,
    lon,
    // "Kulttuurikeskus Villa Rana, 13, Seminaarinkatu, …, Suomi / Finland": the first parts are enough.
    label: `${String(top["display_name"] ?? "")
      .split(", ")
      .slice(0, 4)
      .join(", ")} (© OpenStreetMap contributors)`,
    approximate: false,
  };
};

const CACHE_DIR = join(REPO_ROOT, "data", "cache", "geocode");
const CACHE_MAX_AGE_MS = 30 * 24 * 3_600_000;

/**
 * Finnish addresses, places and towns. Nominatim's policy: an identifying User-Agent,
 * at most one request per second (a CLI makes one), and caching (30 days on disk).
 */
export const geocode = async (address: string, contact?: string): Promise<Located | undefined> => {
  const key = address.trim().toLowerCase().replace(/\s+/g, " ");
  const path = join(CACHE_DIR, `${createHash("sha1").update(key).digest("hex")}.json`);
  try {
    const cached = JSON.parse(await readFile(path, "utf8")) as { storedAt: string; body: unknown };
    if (Date.now() - Date.parse(cached.storedAt) < CACHE_MAX_AGE_MS)
      return parseNominatim(cached.body);
  } catch {
    // not cached
  }
  const url = new URL("https://nominatim.openstreetmap.org/search");
  url.search = new URLSearchParams({
    q: key,
    format: "jsonv2",
    countrycodes: "fi",
    limit: "1",
  }).toString();
  const res = await fetch(url, {
    headers: { accept: "application/json", "user-agent": userAgent(contact) },
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) throw new Error(`Nominatim answered ${res.status}`);
  const body: unknown = await res.json();
  await mkdir(CACHE_DIR, { recursive: true });
  await writeFile(path, JSON.stringify({ storedAt: new Date().toISOString(), key, body }));
  return parseNominatim(body);
};
