import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { GoogleButton } from "../components/auth/GoogleButton";
import { AuthScreen } from "./auth/AuthScreen";

export function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) navigate("/", { replace: true });
  }, [user, navigate]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (password !== confirm) {
      setError("Пароли не совпадают");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await register(username.trim(), password);
      navigate("/", { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Не удалось зарегистрироваться");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthScreen
      title="Создать аккаунт"
      subtitle="Регистрация открывает сохранённые запросы, расписания и алерты."
      footer={
        <>
          Уже есть аккаунт? <Link to="/login">Войти</Link>
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
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </label>
        <label className="field">
          <span className="field__label">Повторите пароль</span>
          <input
            className="input"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
          />
        </label>
        {error ? <p className="auth__error">{error}</p> : null}
        <button type="submit" className="btn btn--primary auth__submit" disabled={busy}>
          {busy ? "Создание…" : "Зарегистрироваться"}
        </button>
      </form>
    </AuthScreen>
  );
}
