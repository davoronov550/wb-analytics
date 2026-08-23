import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { useQueryState } from "../context/QueryContext";
import { QueryBar } from "../components/QueryBar";
import { IconLogout, IconMenu } from "../components/ui/icons";
import "./Topbar.css";

interface TopbarProps {
  onOpenMenu: () => void;
}

function initials(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

export function Topbar({ onOpenMenu }: TopbarProps) {
  const { user, logout } = useAuth();
  const { patchFilters, reload } = useQueryState();
  const navigate = useNavigate();

  const handleParsed = (query: string) => {
    patchFilters({ query });
    reload();
  };

  return (
    <header className="topbar">
      <button
        type="button"
        className="topbar__menu"
        onClick={onOpenMenu}
        aria-label="Открыть меню"
      >
        <IconMenu />
      </button>

      <QueryBar onParsed={handleParsed} />

      <div className="topbar__user">
        {user ? (
          <>
            <Link to="/settings" className="topbar__chip" title="Профиль">
              <span className="topbar__avatar">{initials(user.username)}</span>
              <span className="topbar__username">{user.username}</span>
            </Link>
            <button
              type="button"
              className="btn btn--subtle btn--sm topbar__logout"
              onClick={logout}
              aria-label="Выйти"
            >
              <IconLogout className="topbar__logout-icon" />
              <span className="topbar__logout-label">Выйти</span>
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => navigate("/login")}
            >
              Войти
            </button>
            <button
              type="button"
              className="btn btn--primary btn--sm"
              onClick={() => navigate("/register")}
            >
              Регистрация
            </button>
          </>
        )}
      </div>
    </header>
  );
}
