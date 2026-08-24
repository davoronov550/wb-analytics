import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { GoogleButton } from "../../components/auth/GoogleButton";
import {
  IconAlert,
  IconAnalytics,
  IconCatalog,
  IconHistory,
  IconSchedule,
  IconSaved,
  IconSearch,
  IconSpark,
} from "../../components/ui/icons";
import "./landing.css";

const FEATURES = [
  {
    icon: IconSearch,
    title: "Сбор по запросу",
    text: "Укажите поисковый запрос — сервис соберёт товары с Wildberries: название, цену, скидку, рейтинг и число отзывов.",
  },
  {
    icon: IconCatalog,
    title: "Фильтры и сортировка",
    text: "Диапазон цены, минимальный рейтинг и число отзывов. Комбинированная сортировка сразу по нескольким полям.",
  },
  {
    icon: IconAnalytics,
    title: "Графики и аналитика",
    text: "Распределение цен, связь скидки с рейтингом, агрегаты по выборке и сравнение запросов между собой.",
  },
  {
    icon: IconHistory,
    title: "История цен",
    text: "Каждый сбор сохраняет снимок цены и рейтинга — видно, как менялась стоимость товара во времени.",
  },
  {
    icon: IconSchedule,
    title: "Расписания",
    text: "Периодический сбор по вашим запросам в фоне: данные обновляются без ручного запуска.",
  },
  {
    icon: IconAlert,
    title: "Алерты и экспорт",
    text: "Уведомления при изменении цены и выгрузка отфильтрованной выборки в CSV или XLSX.",
  },
];

const STEPS = [
  { n: "01", title: "Задайте запрос", text: "Введите категорию или поисковую фразу — например «наушники»." },
  { n: "02", title: "Сервис соберёт данные", text: "Парсер обходит выдачу Wildberries и складывает товары в базу." },
  { n: "03", title: "Анализируйте", text: "Фильтруйте, стройте графики, следите за ценами и выгружайте отчёты." },
];

export function LandingPage() {
  const { user, ready } = useAuth();
  const navigate = useNavigate();

  // The landing is for visitors; signed-in users go straight to the workspace.
  useEffect(() => {
    if (ready && user) navigate("/app", { replace: true });
  }, [ready, user, navigate]);

  return (
    <div className="landing">
      <header className="landing__header">
        <div className="landing__container landing__header-inner">
          <Link to="/" className="landing__logo">
            <span className="landing__logo-mark">
              <IconSpark />
            </span>
            <span className="landing__logo-word">WB Analytics</span>
          </Link>
          <nav className="landing__nav" aria-label="Навигация лендинга">
            <a href="#features" className="landing__nav-link">
              Возможности
            </a>
            <a href="#how" className="landing__nav-link">
              Как это работает
            </a>
          </nav>
          <div className="landing__header-actions">
            <Link to="/login" className="btn btn--ghost btn--sm">
              Войти
            </Link>
            <Link to="/register" className="btn btn--primary btn--sm">
              Начать бесплатно
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="landing__hero">
          <div className="landing__container landing__hero-inner">
            <div className="landing__hero-copy">
              <span className="landing__eyebrow">Аналитика маркетплейса</span>
              <h1 className="landing__title">
                Данные Wildberries,
                <br />
                <span className="landing__title-accent">собранные и разобранные</span>
              </h1>
              <p className="landing__lead">
                Соберите товары по любому запросу и разберите выборку по цене, скидке, рейтингу
                и отзывам — с графиками, историей цен, расписаниями и алертами.
              </p>
              <div className="landing__cta">
                <Link to="/register" className="btn btn--primary landing__cta-main">
                  Начать бесплатно
                </Link>
                <Link to="/login" className="btn btn--ghost landing__cta-alt">
                  У меня есть аккаунт
                </Link>
              </div>
              <div className="landing__oauth">
                <span className="landing__oauth-label">или в один клик</span>
                <GoogleButton />
              </div>
            </div>

            <div className="landing__hero-visual" aria-hidden="true">
              <div className="landing__panel">
                <div className="landing__panel-head">
                  <span className="landing__dot" />
                  <span className="landing__dot" />
                  <span className="landing__dot" />
                  <span className="landing__panel-title">Каталог · наушники</span>
                </div>
                <div className="landing__stats">
                  <div className="landing__stat">
                    <span className="landing__stat-label">Товаров</span>
                    <span className="landing__stat-value">801</span>
                  </div>
                  <div className="landing__stat">
                    <span className="landing__stat-label">Медиана</span>
                    <span className="landing__stat-value">1 692 ₽</span>
                  </div>
                  <div className="landing__stat">
                    <span className="landing__stat-label">Со скидкой</span>
                    <span className="landing__stat-value">96,5%</span>
                  </div>
                </div>
                <div className="landing__bars">
                  {[38, 62, 91, 74, 55, 43, 30, 22].map((h, i) => (
                    <span key={i} className="landing__bar" style={{ height: `${h}%` }} />
                  ))}
                </div>
                <div className="landing__rows">
                  {[
                    ["A.Pods PRO 2", "1 692 ₽", "4.8"],
                    ["Микрофон петличный", "890 ₽", "5.0"],
                    ["Наушники JBL", "2 340 ₽", "4.6"],
                  ].map(([name, price, rating]) => (
                    <div key={name} className="landing__row">
                      <span className="landing__row-name">{name}</span>
                      <span className="landing__row-price">{price}</span>
                      <span className="landing__row-rating">★ {rating}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="landing__section" id="features">
          <div className="landing__container">
            <div className="landing__section-head">
              <span className="landing__eyebrow">Возможности</span>
              <h2 className="landing__section-title">Всё для анализа выдачи</h2>
              <p className="landing__section-lead">
                От разового сбора до регулярного мониторинга цен — в одном рабочем пространстве.
              </p>
            </div>
            <ul className="landing__features">
              {FEATURES.map(({ icon: Icon, title, text }) => (
                <li className="landing__feature" key={title}>
                  <span className="landing__feature-icon">
                    <Icon />
                  </span>
                  <h3 className="landing__feature-title">{title}</h3>
                  <p className="landing__feature-text">{text}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="landing__section landing__section--alt" id="how">
          <div className="landing__container">
            <div className="landing__section-head">
              <span className="landing__eyebrow">Как это работает</span>
              <h2 className="landing__section-title">Три шага до первой выборки</h2>
            </div>
            <ol className="landing__steps">
              {STEPS.map((s) => (
                <li className="landing__step" key={s.n}>
                  <span className="landing__step-n">{s.n}</span>
                  <h3 className="landing__step-title">{s.title}</h3>
                  <p className="landing__step-text">{s.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="landing__section">
          <div className="landing__container">
            <div className="landing__final">
              <span className="landing__final-icon">
                <IconSaved />
              </span>
              <h2 className="landing__final-title">Готовы разобрать свою нишу?</h2>
              <p className="landing__final-text">
                Создайте аккаунт — сохранённые запросы, расписания и алерты станут доступны сразу.
              </p>
              <Link to="/register" className="btn btn--primary landing__cta-main">
                Создать аккаунт
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing__footer">
        <div className="landing__container landing__footer-inner">
          <span className="landing__logo-word landing__footer-brand">WB Analytics</span>
          <span className="landing__footer-note">
            Сбор и анализ данных Wildberries для продавцов и аналитиков.
          </span>
        </div>
      </footer>
    </div>
  );
}
