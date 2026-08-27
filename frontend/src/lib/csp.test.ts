import { expect, test } from "vitest";

import { buildCsp } from "./csp";

const API = "http://localhost:8000";

test("locks down the directives an attacker would reach for", () => {
  const policy = buildCsp(API);
  expect(policy).toContain("default-src 'self'");
  expect(policy).toContain("object-src 'none'");
  expect(policy).toContain("frame-ancestors 'none'");
  expect(policy).toContain("base-uri 'self'");
});

test("allows the API origin to be called", () => {
  expect(buildCsp(API)).toContain(`connect-src 'self' ${API}`);
});

test("allows Google Identity Services to load and render", () => {
  const policy = buildCsp(API);
  expect(policy).toContain("script-src 'self' https://accounts.google.com");
  expect(policy).toContain("frame-src https://accounts.google.com");
});

test("production forbids inline scripts", () => {
  expect(buildCsp(API)).not.toContain("script-src 'self' 'unsafe-inline'");
});

test("development allows the HMR client", () => {
  const policy = buildCsp(API, { dev: true });
  expect(policy).toContain("'unsafe-inline'");
  expect(policy).toContain("ws:");
});
