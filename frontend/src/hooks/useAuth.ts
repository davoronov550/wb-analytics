// Auth state now lives in a shared provider so every surface (sidebar, topbar,
// protected routes, pages) reads one source of truth. Kept here as a re-export
// for existing import paths.
export { useAuth } from "../context/AuthContext";
