import { describe, expect, it } from "vitest";
import { loadEnv } from "../src/lib/env.ts";

const DATABASE_URL = "postgres://pgtm:pgtm@localhost:5432/pgtm";

describe("loadEnv", () => {
  it("treats an empty value as unset, as Compose passes one for an unset token", () => {
    const env = loadEnv({ DATABASE_URL, MCP_TOKEN: "", CONTACT: "" });
    expect(env.MCP_TOKEN).toBeUndefined();
    expect(env.CONTACT).toBeUndefined();
  });

  it("still rejects a token that is set but too short", () => {
    expect(() => loadEnv({ DATABASE_URL, MCP_TOKEN: "short" })).toThrow(/MCP_TOKEN/);
  });
});
