import { useEffect, useState } from "react";

import {
  createSavedSearch,
  deleteSavedSearch,
  listSavedSearches,
} from "../../api/savedSearches";
import type { Filters, SavedSearch } from "../../types";
import "../ui/manager.css";

interface Props {
  filters: Filters;
  onApply: (saved: SavedSearch) => void;
}

/** List and manage the user's saved searches. */
export function SavedSearches({ filters, onApply }: Props) {
  const [items, setItems] = useState<SavedSearch[]>([]);
  const [name, setName] = useState("");

  const reload = () => listSavedSearches().then(setItems).catch(() => setItems([]));

  useEffect(() => {
    reload();
  }, []);

  const save = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    await createSavedSearch(trimmed, filters.query ?? "", filters as Record<string, unknown>);
    setName("");
    await reload();
  };

  const remove = async (id: number) => {
    await deleteSavedSearch(id);
    await reload();
  };

  return (
    <section className="manager">
      <div className="manager__form">
        <input
          className="input"
          aria-label="Название запроса"
          placeholder="Название текущего фильтра"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button type="button" className="btn btn--primary" onClick={save}>
          Сохранить текущий
        </button>
      </div>

      {items.length === 0 ? (
        <p className="manager__empty">
          Сохранённых запросов пока нет — настройте фильтры и сохраните набор.
        </p>
      ) : (
        <ul className="manager__list">
          {items.map((item) => (
            <li key={item.id} className="manager__item">
              <span className="manager__item-main">
                <button type="button" className="manager__link" onClick={() => onApply(item)}>
                  {item.name}
                </button>
                {item.query ? <span className="manager__item-meta">{item.query}</span> : null}
              </span>
              <span className="manager__actions">
                <button
                  type="button"
                  className="btn btn--danger btn--sm"
                  onClick={() => remove(item.id)}
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
