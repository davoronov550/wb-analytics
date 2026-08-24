/** The workspace is auth-only: guests are sent to /login, members get through. */
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

import { ProtectedRoute } from "./ProtectedRoute";

const authState = { user: null as { id: number; username: string } | null, ready: true };
vi.mock("../../context/AuthContext", () => ({ useAuth: () => authState }));

beforeEach(() => {
  authState.user = null;
  authState.ready = true;
});

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<h1>Вход</h1>} />
        <Route
          path="/app"
          element={
            <ProtectedRoute>
              <h1>Обзор</h1>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

test("sends a guest to the login screen", () => {
  renderAt("/app");
  expect(screen.getByRole("heading", { name: "Вход" })).toBeInTheDocument();
});

test("renders the workspace for a signed-in user", () => {
  authState.user = { id: 1, username: "user" };
  renderAt("/app");
  expect(screen.getByRole("heading", { name: "Обзор" })).toBeInTheDocument();
});

test("waits for auth bootstrap before deciding", () => {
  authState.ready = false;
  renderAt("/app");
  expect(screen.queryByRole("heading", { name: "Вход" })).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Обзор" })).not.toBeInTheDocument();
});
