import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { chromium } from "playwright";

/**
 * Finnkino's API needs Vista's public client token (a JWT, valid 12 h). Vista documents it
 * as "safe to make available to public facing clients", and Finnkino embeds it in its
 * front page. That page sits behind a Cloudflare check that only a real, visible browser
 * passes (plain HTTP and headless Chrome are both challenged, even from a home
 * connection), so we open the locally installed Chrome, read the token, and cache it.
 *
 * This only works on a desktop machine with Chrome, never in CI or the cloud.
 */

const FRONT_PAGE = "https://www.finnkino.fi/";
const JWT = /eyJ[\w-]{20,}\.[\w-]{20,}\.[\w-]{20,}/;
/** Get a new token when less than this is left. */
const MIN_VALIDITY_MS = 60 * 60 * 1000;

export type Token = { token: string; expiresAt: string };

export const tokenExpiry = (token: string): Date => {
  const payload = JSON.parse(Buffer.from(token.split(".")[1] ?? "", "base64url").toString()) as {
    exp?: unknown;
  };
  if (typeof payload.exp !== "number") throw new Error("Finnkino token has no exp claim");
  return new Date(payload.exp * 1000);
};

export const isFresh = (token: Token, now: Date): boolean =>
  Date.parse(token.expiresAt) - now.getTime() > MIN_VALIDITY_MS;

/** Opens a visible Chrome window for a few seconds. */
export const readTokenWithBrowser = async (): Promise<string> => {
  const browser = await chromium.launch({ channel: "chrome", headless: false });
  try {
    const page = await browser.newPage();
    await page.goto(FRONT_PAGE, { waitUntil: "domcontentloaded", timeout: 45_000 });
    // Cloudflare's check resolves itself in a real browser; poll until the page has the token.
    const deadline = Date.now() + 45_000;
    while (Date.now() < deadline) {
      const token = (await page.content()).match(JWT)?.[0];
      if (token) return token;
      await page.waitForTimeout(1000);
    }
    throw new Error("No token found on finnkino.fi (Cloudflare check not passed?)");
  } finally {
    await browser.close();
  }
};

export type TokenSource = {
  cachePath: string;
  now?: () => Date;
  /** Injected in tests. */
  readToken?: () => Promise<string>;
};

/** Cached token if it is still valid for a while, otherwise a fresh one from the browser. */
export const getToken = async ({
  cachePath,
  now = () => new Date(),
  readToken = readTokenWithBrowser,
}: TokenSource): Promise<string> => {
  try {
    const cached = JSON.parse(await readFile(cachePath, "utf8")) as Token;
    if (isFresh(cached, now())) return cached.token;
  } catch {
    // no cache yet
  }
  const token = await readToken();
  const entry: Token = { token, expiresAt: tokenExpiry(token).toISOString() };
  await mkdir(dirname(cachePath), { recursive: true });
  await writeFile(cachePath, JSON.stringify(entry), { mode: 0o600 });
  return token;
};
