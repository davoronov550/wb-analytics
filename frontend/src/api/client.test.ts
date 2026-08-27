/** The SPA must refresh silently: a 30-minute access token would otherwise
 *  bounce the user out mid-session. */
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { authedFetch } from "./client";
import { getToken, setTokens } from "./token";

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

const ok = { ok: true, status: 200, json: async () => ({}) };
const unauthorized = { ok: false, status: 401, json: async () => ({}) };

test("passes the access token through", async () => {
  setTokens("acc", "ref");
  const fetchMock = vi.fn().mockResolvedValue(ok);
  vi.stubGlobal("fetch", fetchMock);

  await authedFetch("/api/thing/");

  expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer acc");
});

test("on 401 it refreshes and retries once", async () => {
  setTokens("stale", "ref");
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(unauthorized) // original call
    .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ access: "fresh" }) })
    .mockResolvedValueOnce(ok); // retry
  vi.stubGlobal("fetch", fetchMock);

  const response = await authedFetch("/api/thing/");

  expect(response.status).toBe(200);
  expect(getToken()).toBe("fresh");
  expect(fetchMock).toHaveBeenCalledTimes(3);
});

test("stores a rotated refresh token", async () => {
  setTokens("stale", "ref");
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(unauthorized)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ access: "fresh", refresh: "rotated" }),
      })
      .mockResolvedValueOnce(ok),
  );

  await authedFetch("/api/thing/");

  const { getRefreshToken } = await import("./token");
  expect(getRefreshToken()).toBe("rotated");
});

test("a failed refresh clears the session instead of looping", async () => {
  setTokens("stale", "dead");
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(unauthorized)
    .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) });
  vi.stubGlobal("fetch", fetchMock);

  const response = await authedFetch("/api/thing/");

  expect(response.status).toBe(401);
  expect(getToken()).toBeNull();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

test("without a refresh token it does not attempt a refresh", async () => {
  setTokens("stale");
  const fetchMock = vi.fn().mockResolvedValue(unauthorized);
  vi.stubGlobal("fetch", fetchMock);

  await authedFetch("/api/thing/");

  expect(fetchMock).toHaveBeenCalledTimes(1);
});
