import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { IconSpark } from "../../components/ui/icons";
import "./auth.css";

const HIGHLIGHTS = [
  "Сбор товаров Wildberries по любому запросу",
  "Фильтры, сортировка и живые графики",
  "История цен, расписания и алерты",
];

export function AuthScreen({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <div className="auth">
      <aside className="auth__brand">
        <Link to="/" className="auth__logo">
          <span className="auth__logo-mark">
            <IconSpark />
          </span>
          <span className="auth__logo-word">WB Analytics</span>
        </Link>
        <div className="auth__pitch">
          <h2 className="auth__pitch-title">Аналитика товаров Wildberries — в одном месте.</h2>
          <ul className="auth__highlights">
            {HIGHLIGHTS.map((h) => (
              <li key={h}>
                <span className="auth__check" aria-hidden="true">
                  ✓
                </span>
                {h}
              </li>
            ))}
          </ul>
        </div>
        <p className="auth__brand-foot">Сбор и анализ данных для продавцов и аналитиков.</p>
      </aside>

      <main className="auth__panel">
        <div className="auth__card">
          <header className="auth__head">
            <h1 className="auth__title">{title}</h1>
            <p className="auth__subtitle">{subtitle}</p>
          </header>
          {children}
          <div className="auth__foot">{footer}</div>
        </div>
      </main>
    </div>
  );
}
