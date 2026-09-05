import { describe, expect, it } from "vitest";
import { API_PREFIX, apiUrl } from "./endpoint";

/** Sources of the sibling API modules, read through Vite rather than `node:fs`
 *  — the project ships no `@types/node`, and pulling it in for one test would
 *  be a dependency added to make an assertion compile. */
const SOURCES = import.meta.glob("./*.ts", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

/** The API modules, excluding this file, the other tests, and `endpoint.ts`
 *  itself — it is the one place allowed to know the origin and the prefix. */
function apiSources(): { name: string; text: string }[] {
  return Object.entries(SOURCES)
    .filter(([path]) => !path.endsWith(".test.ts") && !path.endsWith("/endpoint.ts"))
    .map(([path, text]) => ({ name: path.replace("./", ""), text }));
}

describe("apiUrl", () => {
  it("puts the version prefix between the origin and the path", () => {
    // Asserted by shape, not by value: the origin comes from VITE_API_BASE and
    // differs between a developer's .env and CI, so pinning it here would make
    // the test fail on someone's machine for a reason unrelated to the prefix.
    expect(apiUrl("/products/")).toMatch(/^https?:\/\/[^/]+\/v1\/products\/$/);
  });

  it("keeps the query string attached to the path", () => {
    expect(apiUrl("/stats/?query=a")).toContain("/v1/stats/?query=a");
  });
});

describe("no module addresses the API on its own", () => {
  // The eleven copies of the base URL are why moving to /v1 touched eleven
  // files. Reintroducing one is easy and invisible: the module keeps working,
  // against the wrong prefix, until Django stops answering the old one.
  it("no API module builds a URL from the environment directly", () => {
    const offenders = apiSources()
      .filter(({ text }) => text.includes("VITE_API_BASE"))
      .map(({ name }) => name);

    expect(offenders).toEqual([]);
  });

  it("no API module hardcodes a version prefix", () => {
    const offenders = apiSources()
      .filter(({ text }) => /["'`]\/(v\d+|api)\//.test(text))
      .map(({ name }) => name);

    expect(offenders).toEqual([]);
  });

  it("the sources were actually read", () => {
    // Guards the guard twice over: an empty glob would report every module
    // clean, which is precisely the failure the two checks above exist to
    // avoid. `products.ts` must be among what was read.
    const names = apiSources().map(({ name }) => name);

    expect(names).toContain("products.ts");
    expect(names).not.toContain("endpoint.ts");
    expect(apiSources().every(({ text }) => text.length > 0)).toBe(true);
  });

  it("the detector actually matches a hardcoded prefix", () => {
    // Guards the guard: a regex that matches nothing reports every file clean.
    expect(/["'`]\/(v\d+|api)\//.test('fetch("/api/products/")')).toBe(true);
    expect(/["'`]\/(v\d+|api)\//.test('apiUrl("/products/")')).toBe(false);
  });

  it("the prefix is the one Django and the gateway both answer", () => {
    expect(API_PREFIX).toBe("/v1");
  });
});
