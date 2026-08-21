import { useEffect, useState } from "react";

import {
  createSavedSearch,
  deleteSavedSearch,
  listSavedSearches,
} from "../../api/savedSearches";
import type { Filters, SavedSearch } from "../../types";

interface Props {
  filters: Filters;
  onApply: (saved: SavedSearch) => void;
}

/** List and manage the user's saved searches (FE-09). */
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
    <section className="saved-searches">
      <h2>Сохранённые запросы</h2>
      <div className="saved-searches__form">
        <input
          aria-label="Название запроса"
          placeholder="Название текущего фильтра"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button type="button" onClick={save}>
          Сохранить текущий
        </button>
      </div>
      <ul className="saved-searches__list">
        {items.map((item) => (
          <li key={item.id}>
            <button type="button" onClick={() => onApply(item)}>
              {item.name}
            </button>
            <button type="button" onClick={() => remove(item.id)}>
              Удалить
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
