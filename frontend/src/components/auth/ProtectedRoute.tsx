import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { Spinner } from "../ui/primitives";

/** Gate for authenticated-only routes: waits for auth bootstrap, then either
 * renders the page or redirects to /login (preserving the intended path). */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  const location = useLocation();

  if (!ready) return <Spinner label="Загрузка…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}
