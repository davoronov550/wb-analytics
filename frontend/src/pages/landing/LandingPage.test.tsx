/** Landing page: renders the pitch + auth CTAs, and hands signed-in users to /app. */
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

import { LandingPage } from "./LandingPage";

const authState = { user: null as { id: number; username: string } | null, ready: true };

vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({ ...authState, loginWithGoogle: vi.fn() }),
}));

// The Google button pulls in the GSI script; stub it out for the render tests.
vi.mock("../../components/auth/GoogleButton", () => ({
  GoogleButton: () => <div data-testid="google-button" />,
}));

beforeEach(() => {
  authState.user = null;
  authState.ready = true;
});

function renderAt(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/app" element={<h1>Рабочее пространство</h1>} />
      </Routes>
    </MemoryRouter>,
  );
}

test("shows the product pitch and both auth calls to action", () => {
  renderAt();
  expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: /Начать бесплатно/ })[0]).toHaveAttribute(
    "href",
    "/register",
  );
  expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute("href", "/login");
});

test("lists the service capabilities and the how-it-works steps", () => {
  renderAt();
  expect(screen.getByText("Сбор по запросу")).toBeInTheDocument();
  expect(screen.getByText("История цен")).toBeInTheDocument();
  expect(screen.getByText("Алерты и экспорт")).toBeInTheDocument();
  expect(screen.getByText("Задайте запрос")).toBeInTheDocument();
});

test("offers one-click Google sign-in", () => {
  renderAt();
  expect(screen.getByTestId("google-button")).toBeInTheDocument();
});

test("redirects an authenticated visitor to the workspace", () => {
  authState.user = { id: 1, username: "user" };
  renderAt();
  expect(screen.getByRole("heading", { name: "Рабочее пространство" })).toBeInTheDocument();
});
