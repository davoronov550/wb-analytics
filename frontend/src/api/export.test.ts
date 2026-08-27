import { afterEach, expect, test, vi } from "vitest";

import { buildExportUrl, downloadExport } from "./export";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

test("builds the URL from the active filters", () => {
  const url = buildExportUrl({ minPrice: 100, query: "наушники" }, "csv");
  expect(url).toContain("min_price=100");
  expect(url).toContain("format=csv");
});

test("sends the bearer token — export is authenticated", async () => {
  localStorage.setItem("wb_token", "tok-123");
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    blob: async () => new Blob(["a,b"], { type: "text/csv" }),
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("URL", { ...URL, createObjectURL: () => "blob:x", revokeObjectURL: () => {} });

  await downloadExport({}, "csv");

  const headers = fetchMock.mock.calls[0][1].headers;
  expect(headers.Authorization).toBe("Bearer tok-123");
});

test("surfaces a readable message when the session is missing", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 }));
  await expect(downloadExport({}, "csv")).rejects.toThrow(/Войдите/);
});
