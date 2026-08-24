import { type FormEvent, useEffect, useState } from "react";

import {
  createSchedule,
  deleteSchedule,
  listSchedules,
  setScheduleActive,
} from "../../api/schedules";
import type { Schedule } from "../../types";

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
    <section className="schedules">
      <h2>Расписания сбора</h2>
      <form className="schedules__form" onSubmit={submit}>
        <input
          aria-label="Запрос расписания"
          placeholder="Запрос (напр. наушники)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select aria-label="Интервал" value={spec} onChange={(e) => setSpec(e.target.value)}>
          {SPEC_PRESETS.map((preset) => (
            <option key={preset} value={preset}>
              {preset}
            </option>
          ))}
        </select>
        <button type="submit">Добавить</button>
      </form>
      {error ? <p className="schedules__error">{error}</p> : null}
      <ul className="schedules__list">
        {schedules.map((schedule) => (
          <li key={schedule.id} className="schedules__item">
            <span>
              {schedule.query} · {schedule.spec} · {schedule.active ? "активно" : "выключено"}
            </span>
            <button type="button" onClick={() => toggle(schedule)}>
              {schedule.active ? "Выключить" : "Включить"}
            </button>
            <button type="button" onClick={() => remove(schedule.id)}>
              Удалить
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
