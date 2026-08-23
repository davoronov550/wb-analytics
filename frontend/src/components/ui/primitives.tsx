import type { ReactNode } from "react";

import "./primitives.css";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="page-header__text">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1 className="page-header__title">{title}</h1>
        {description ? <p className="page-header__desc">{description}</p> : null}
      </div>
      {actions ? <div className="page-header__actions">{actions}</div> : null}
    </header>
  );
}

export function Panel({
  title,
  subtitle,
  actions,
  padded = true,
  className = "",
  children,
}: {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  padded?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`panel ${className}`}>
      {title || actions ? (
        <div className="panel__head">
          <div>
            {title ? <h2 className="panel__title">{title}</h2> : null}
            {subtitle ? <p className="panel__subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="panel__actions">{actions}</div> : null}
        </div>
      ) : null}
      <div className={padded ? "panel__body" : "panel__body panel__body--flush"}>{children}</div>
    </section>
  );
}

export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon?: ReactNode;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      {icon ? <div className="empty-state__icon">{icon}</div> : null}
      <p className="empty-state__title">{title}</p>
      {hint ? <p className="empty-state__hint">{hint}</p> : null}
      {action ? <div className="empty-state__action">{action}</div> : null}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="spinner" role="status">
      <span className="spinner__ring" aria-hidden="true" />
      {label ? <span className="spinner__label">{label}</span> : null}
    </div>
  );
}

export function StatTile({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string;
  value: ReactNode;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div className={`stat-tile${accent ? " stat-tile--accent" : ""}`}>
      <p className="stat-tile__label">{label}</p>
      <p className="stat-tile__value">{value}</p>
      {sub ? <p className="stat-tile__sub">{sub}</p> : null}
    </div>
  );
}
