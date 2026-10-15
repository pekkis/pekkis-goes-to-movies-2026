import { describe, expect, it, vi } from "vitest";
import type { HttpClient } from "../../../src/lib/http.ts";
import { fetchNexxo } from "../../../src/providers/nexxo/fetch.ts";
import { NEXXO_SITES } from "../../../src/providers/nexxo/sites.ts";

const site = (provider: string) => NEXXO_SITES.find((s) => s.provider === provider)!;

const fakeHttp = () => {
  const getJson = vi.fn(async () => ({ shows: [] }));
  const http: HttpClient = { getJson, getText: vi.fn(), postForm: vi.fn() };
  return { http, getJson };
};

describe("fetchNexxo", () => {
  it("asks for all films: newer plugins answer nothing without movieid", async () => {
    const { http, getJson } = fakeHttp();
    await fetchNexxo(http, site("biosalo"), { from: "2026-10-15", days: 7, today: "2026-10-15" });
    expect(getJson).toHaveBeenCalledWith(
      "https://biosalo.fi/wp-content/plugins/nexxo-scope/public_api.php",
      expect.objectContaining({ action: "exportdailyshows", locationid: "1", movieid: 0 }),
    );
  });

  it("reads a sister cinema from the host that serves its data, one request per location", async () => {
    const { http, getJson } = fakeHttp();
    await fetchNexxo(http, site("biostara"), { from: "2026-10-15", days: 7, today: "2026-10-15" });
    expect(getJson).toHaveBeenCalledTimes(1);
    expect(getJson).toHaveBeenCalledWith(
      "https://biosalo.fi/wp-content/plugins/nexxo-scope/public_api.php",
      expect.objectContaining({ locationid: "2" }),
    );
  });
});
