import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./layout/AppShell";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { LandingPage } from "./pages/landing/LandingPage";
import { OverviewPage } from "./pages/OverviewPage";
import { ProductsPage } from "./pages/ProductsPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { HistoryPage } from "./pages/HistoryPage";
import { SchedulesPage } from "./pages/SchedulesPage";
import { AlertsPage } from "./pages/AlertsPage";
import { SavedPage } from "./pages/SavedPage";
import { SettingsPage } from "./pages/SettingsPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import "./pages/pages.css";

export default function App() {
  return (
    <Routes>
      {/* Public: landing + auth screens. */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* The whole workspace sits behind authentication. */}
      <Route
        path="/app"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<OverviewPage />} />
        <Route path="products" element={<ProductsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="schedules" element={<SchedulesPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="saved" element={<SavedPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
