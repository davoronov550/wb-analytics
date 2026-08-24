import { type FormEvent, useEffect, useState } from "react";

import {
  createSchedule,
  deleteSchedule,
  listSchedules,
  setScheduleActive,
} from "../../api/schedules";
import type { Schedule } from "../../types";
import "../ui/manager.css";

const SPEC_PRESETS = ["every 1h", "every 6h", "every 12h", "every 1d"];

/** Manage periodic collection schedules. */
export function ScheduleManager() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [query, setQuery] = useState("");
  const [spec, setSpec] = useState(SPEC_PRESETS[1]);
  const [error, setError] = useState<string | null>(null);

  const reload = () =>
    listSchedules()
      .then(setSchedules)
      .catch((err: unknown) => setError(String(err)));

  useEffect(() => {
    reload();
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    setError(null);
    try {
      await createSchedule(trimmed, spec);
      setQuery("");
      await reload();
    } catch (err: unknown) {
      setError(String(err));
    }
  };

  const toggle = async (schedule: Schedule) => {
    await setScheduleActive(schedule.id, !schedule.active);
    await reload();
  };

  const remove = async (id: number) => {
    await deleteSchedule(id);
    await reload();
  };

  return (
    <section className="manager">
      <form className="manager__form" onSubmit={submit}>
        <input
          className="input"
          aria-label="Запрос расписания"
          placeholder="Запрос (напр. наушники)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          className="select"
          aria-label="Интервал"
          value={spec}
          onChange={(e) => setSpec(e.target.value)}
        >
          {SPEC_PRESETS.map((preset) => (
            <option key={preset} value={preset}>
              {preset}
            </option>
          ))}
        </select>
        <button type="submit" className="btn btn--primary">
          Добавить
        </button>
      </form>

      {error ? <p className="manager__error">{error}</p> : null}

      {schedules.length === 0 ? (
        <p className="manager__empty">Расписаний пока нет — добавьте первое выше.</p>
      ) : (
        <ul className="manager__list">
          {schedules.map((schedule) => (
            <li key={schedule.id} className="manager__item">
              <span className="manager__item-main">
                <span className="manager__item-title">{schedule.query}</span>
                <span className="manager__item-meta">{schedule.spec}</span>
                <span className={`badge ${schedule.active ? "badge--success" : ""}`}>
                  {schedule.active ? "активно" : "выключено"}
                </span>
              </span>
              <span className="manager__actions">
                <button
                  type="button"
                  className="btn btn--subtle btn--sm"
                  onClick={() => toggle(schedule)}
                >
                  {schedule.active ? "Выключить" : "Включить"}
                </button>
                <button
                  type="button"
                  className="btn btn--danger btn--sm"
                  onClick={() => remove(schedule.id)}
                >
                  Удалить
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
