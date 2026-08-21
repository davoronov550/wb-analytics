import { type FormEvent, useState } from "react";

interface Props {
  onLogin: (username: string, password: string) => Promise<void>;
  onRegister: (username: string, password: string) => Promise<void>;
}

/** Login / register form (FE-09). */
export function LoginForm({ onLogin, onRegister }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const run = async (action: (u: string, p: string) => Promise<void>) => {
    setError(null);
    try {
      await action(username.trim(), password);
    } catch (err: unknown) {
      setError(String(err));
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void run(onLogin);
  };

  return (
    <form className="login-form" onSubmit={submit}>
      <input
        aria-label="Логин"
        placeholder="Логин"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
      />
      <input
        aria-label="Пароль"
        type="password"
        placeholder="Пароль"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <button type="submit">Войти</button>
      <button type="button" onClick={() => void run(onRegister)}>
        Регистрация
      </button>
      {error ? <span className="login-form__error">{error}</span> : null}
    </form>
  );
}
