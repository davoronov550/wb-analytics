import { type FormEvent, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { GoogleButton } from "../components/auth/GoogleButton";
import { AuthScreen } from "./auth/AuthScreen";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const from = (location.state as { from?: string } | null)?.from ?? "/app";

  useEffect(() => {
    if (user) navigate(from, { replace: true });
  }, [user, from, navigate]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username.trim(), password);
      navigate(from, { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Не удалось войти");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthScreen
      title="С возвращением"
      subtitle="Войдите, чтобы сохранять запросы, настраивать расписания и алерты."
      footer={
        <>
          Нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
        </>
      }
    >
      <div className="auth__oauth">
        <GoogleButton onError={setError} />
      </div>
      <div className="auth__divider">
        <span>или через логин</span>
      </div>
      <form className="auth__form" onSubmit={submit}>
        <label className="field">
          <span className="field__label">Логин</span>
          <input
            className="input"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label className="field">
          <span className="field__label">Пароль</span>
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error ? <p className="auth__error">{error}</p> : null}
        <button type="submit" className="btn btn--primary auth__submit" disabled={busy}>
          {busy ? "Вход…" : "Войти"}
        </button>
      </form>
    </AuthScreen>
  );
}
