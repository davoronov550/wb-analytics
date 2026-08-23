import { NavLink } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import {
  IconAlert,
  IconAnalytics,
  IconCatalog,
  IconChevron,
  IconHistory,
  IconLock,
  IconOverview,
  IconSaved,
  IconSchedule,
  IconSettings,
  IconSpark,
} from "../components/ui/icons";
import "./Sidebar.css";

interface NavItem {
  to: string;
  label: string;
  icon: (p: { className?: string }) => JSX.Element;
  end?: boolean;
  gated?: boolean;
}

interface NavGroup {
  heading: string;
  items: NavItem[];
}

const GROUPS: NavGroup[] = [
  {
    heading: "Данные",
    items: [
      { to: "/", label: "Обзор", icon: IconOverview, end: true },
      { to: "/products", label: "Каталог", icon: IconCatalog },
      { to: "/analytics", label: "Аналитика", icon: IconAnalytics },
      { to: "/history", label: "История цен", icon: IconHistory },
    ],
  },
  {
    heading: "Автоматизация",
    items: [
      { to: "/schedules", label: "Расписания", icon: IconSchedule, gated: true },
      { to: "/alerts", label: "Алерты", icon: IconAlert, gated: true },
      { to: "/saved", label: "Сохранённые", icon: IconSaved, gated: true },
    ],
  },
];

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onNavigate?: () => void;
}

export function Sidebar({ collapsed, onToggleCollapsed, onNavigate }: SidebarProps) {
  const { user } = useAuth();

  const renderItem = (item: NavItem) => {
    const Icon = item.icon;
    const locked = item.gated && !user;
    return (
      <li key={item.to}>
        <NavLink
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) => `nav-item${isActive ? " nav-item--active" : ""}`}
          title={collapsed ? item.label : undefined}
        >
          <span className="nav-item__icon">
            <Icon />
          </span>
          <span className="nav-item__label">{item.label}</span>
          {locked ? (
            <span className="nav-item__lock" title="Требуется вход">
              <IconLock className="nav-item__lock-icon" />
            </span>
          ) : null}
        </NavLink>
      </li>
    );
  };

  return (
    <div className={`sidebar${collapsed ? " sidebar--collapsed" : ""}`}>
      <div className="sidebar__brand">
        <span className="sidebar__logo">
          <IconSpark />
        </span>
        <span className="sidebar__wordmark">
          WB<span className="sidebar__wordmark-accent"> Analytics</span>
        </span>
      </div>

      <nav className="sidebar__nav" aria-label="Основная навигация">
        {GROUPS.map((group) => (
          <div className="sidebar__group" key={group.heading}>
            <p className="sidebar__group-heading">{group.heading}</p>
            <ul className="sidebar__list">{group.items.map(renderItem)}</ul>
          </div>
        ))}
      </nav>

      <div className="sidebar__footer">
        <ul className="sidebar__list">
          {renderItem({ to: "/settings", label: "Профиль", icon: IconSettings, gated: true })}
        </ul>
        <button
          type="button"
          className="sidebar__collapse"
          onClick={onToggleCollapsed}
          aria-label={collapsed ? "Развернуть меню" : "Свернуть меню"}
        >
          <IconChevron className={`sidebar__collapse-icon${collapsed ? "" : " is-open"}`} />
          <span className="nav-item__label">Свернуть</span>
        </button>
      </div>
    </div>
  );
}
