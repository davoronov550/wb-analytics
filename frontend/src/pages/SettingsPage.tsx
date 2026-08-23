import { useAuth } from "../context/AuthContext";
import { PageHeader, Panel, StatTile } from "../components/ui/primitives";
import { IconLogout } from "../components/ui/icons";

const PROVIDER_LABEL: Record<string, string> = {
  password: "Логин / пароль",
  google: "Google",
};

export function SettingsPage() {
  const { user, logout } = useAuth();
  if (!user) return null;

  const providers = user.providers?.length ? user.providers : ["password"];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Аккаунт"
        title="Профиль"
        description="Данные вашей учётной записи и подключённые способы входа."
      />

      <div className="grid grid--3 page__section">
        <StatTile label="Пользователь" value={user.username} accent />
        <StatTile label="Email" value={user.email || "—"} />
        <StatTile label="ID" value={`#${user.id}`} />
      </div>

      <Panel className="page__section" title="Способы входа" subtitle="Подключённые провайдеры авторизации">
        <div className="provider-list">
          {providers.map((p) => (
            <div className="provider-item" key={p}>
              <span className="provider-item__name">{PROVIDER_LABEL[p] ?? p}</span>
              <span className="badge badge--success">Подключён</span>
            </div>
          ))}
        </div>
      </Panel>

      <Panel className="page__section" title="Сессия">
        <button type="button" className="btn btn--danger" onClick={logout}>
          <IconLogout className="topbar__logout-icon" />
          Выйти из аккаунта
        </button>
      </Panel>
    </div>
  );
}
