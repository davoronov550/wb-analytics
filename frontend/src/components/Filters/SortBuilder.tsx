import { useEffect, useRef, useState } from "react";

import type { OrderableField, Sort } from "../../types";
import { DEFAULT_SORT, SORT_FIELDS, fieldLabel } from "../../lib/sortFields";
import { IconChevron, IconClose, IconSort } from "../ui/icons";
import "./SortBuilder.css";

interface Props {
  sortKeys: Sort[];
  onChange: (keys: Sort[]) => void;
}

interface Preset {
  label: string;
  keys: Sort[];
}

const PRESETS: Preset[] = [
  { label: "Отзывы ↓", keys: [{ field: "reviews_count", descending: true }] },
  {
    label: "Рейтинг ↓, затем отзывы ↓",
    keys: [
      { field: "rating", descending: true },
      { field: "reviews_count", descending: true },
    ],
  },
  {
    label: "Цена со скидкой ↑, затем рейтинг ↓",
    keys: [
      { field: "sale_price", descending: false },
      { field: "rating", descending: true },
    ],
  },
];

// Sensible default direction when a field is first added to the sort.
const defaultDescending = (field: OrderableField): boolean =>
  field === "reviews_count" || field === "rating";

const sameKeys = (a: Sort[], b: Sort[]) =>
  a.length === b.length &&
  a.every((k, i) => k.field === b[i].field && k.descending === b[i].descending);

export function SortBuilder({ sortKeys, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  const used = new Set(sortKeys.map((k) => k.field));
  const firstUnused = SORT_FIELDS.find((f) => !used.has(f.field))?.field;

  const setField = (index: number, field: OrderableField) => {
    const next = sortKeys.map((k, i) =>
      i === index ? { field, descending: defaultDescending(field) } : k,
    );
    onChange(next);
  };
  const toggleDir = (index: number) =>
    onChange(sortKeys.map((k, i) => (i === index ? { ...k, descending: !k.descending } : k)));
  const remove = (index: number) => onChange(sortKeys.filter((_, i) => i !== index));
  const move = (index: number, delta: number) => {
    const j = index + delta;
    if (j < 0 || j >= sortKeys.length) return;
    const next = [...sortKeys];
    [next[index], next[j]] = [next[j], next[index]];
    onChange(next);
  };
  const add = () => {
    if (!firstUnused) return;
    onChange([...sortKeys, { field: firstUnused, descending: defaultDescending(firstUnused) }]);
  };

  return (
    <div className="sort-builder" ref={ref}>
      <button
        type="button"
        className="btn btn--ghost btn--sm sort-builder__trigger"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <IconSort className="sort-builder__icon" />
        Сортировка
        {sortKeys.length > 0 ? <span className="badge badge--accent">{sortKeys.length}</span> : null}
      </button>

      {open ? (
        <div className="sort-builder__panel" role="dialog" aria-label="Настройка сортировки">
          <div className="sort-builder__presets">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                className={`sort-builder__preset${sameKeys(p.keys, sortKeys) ? " is-active" : ""}`}
                onClick={() => onChange(p.keys)}
              >
                {p.label}
              </button>
            ))}
          </div>

          <div className="sort-builder__rows">
            {sortKeys.length === 0 ? (
              <p className="sort-builder__empty">Сортировка не задана.</p>
            ) : (
              sortKeys.map((key, index) => (
                <div className="sort-row" key={`${key.field}-${index}`}>
                  <span className="sort-row__order">{index + 1}</span>
                  <select
                    className="sort-row__field"
                    value={key.field}
                    onChange={(e) => setField(index, e.target.value as OrderableField)}
                  >
                    {SORT_FIELDS.map((f) => (
                      <option
                        key={f.field}
                        value={f.field}
                        disabled={f.field !== key.field && used.has(f.field)}
                      >
                        {f.label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="sort-row__dir"
                    onClick={() => toggleDir(index)}
                    title={key.descending ? "По убыванию" : "По возрастанию"}
                  >
                    {key.descending ? "↓ убыв." : "↑ возр."}
                  </button>
                  <div className="sort-row__move">
                    <button
                      type="button"
                      onClick={() => move(index, -1)}
                      disabled={index === 0}
                      aria-label="Выше"
                    >
                      <IconChevron className="sort-row__up" />
                    </button>
                    <button
                      type="button"
                      onClick={() => move(index, 1)}
                      disabled={index === sortKeys.length - 1}
                      aria-label="Ниже"
                    >
                      <IconChevron className="sort-row__down" />
                    </button>
                  </div>
                  <button
                    type="button"
                    className="sort-row__remove"
                    onClick={() => remove(index)}
                    aria-label={`Убрать ${fieldLabel(key.field)}`}
                  >
                    <IconClose />
                  </button>
                </div>
              ))
            )}
          </div>

          <div className="sort-builder__actions">
            <button
              type="button"
              className="btn btn--subtle btn--sm"
              onClick={add}
              disabled={!firstUnused}
            >
              + Добавить уровень
            </button>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => onChange([DEFAULT_SORT])}
            >
              Сбросить
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
