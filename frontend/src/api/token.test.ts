import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { authHeaders, clearTokens, getRefreshToken, getToken, setTokens } from "./token";

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

test("stores both tokens — refresh is what keeps the session alive", () => {
  setTokens("acc", "ref");
  expect(getToken()).toBe("acc");
  expect(getRefreshToken()).toBe("ref");
});

test("a refresh-only update keeps the existing refresh token", () => {
  setTokens("acc", "ref");
  setTokens("acc2");
  expect(getToken()).toBe("acc2");
  expect(getRefreshToken()).toBe("ref");
});

test("clearing removes both", () => {
  setTokens("acc", "ref");
  clearTokens();
  expect(getToken()).toBeNull();
  expect(getRefreshToken()).toBeNull();
});

test("authHeaders is empty when signed out", () => {
  expect(authHeaders()).toEqual({});
});
