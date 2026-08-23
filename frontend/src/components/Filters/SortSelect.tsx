import { useQueryState } from "../../context/QueryContext";
import { IconSort } from "../ui/icons";
import type { Sort } from "../../types";

interface Option {
  label: string;
  sort: Sort;
}

/** Explicit sort presets. Prices sort by the discounted (sale) price per the
 *  product requirement; rating offers best→worst and worst→best. */
const OPTIONS: Option[] = [
  { label: "Отзывы: сначала популярные", sort: { field: "reviews_count", descending: true } },
  { label: "Рейтинг: сначала лучшие", sort: { field: "rating", descending: true } },
  { label: "Рейтинг: сначала худшие", sort: { field: "rating", descending: false } },
  { label: "Цена со скидкой: сначала дешевле", sort: { field: "sale_price", descending: false } },
  { label: "Цена со скидкой: сначала дороже", sort: { field: "sale_price", descending: true } },
];

const keyOf = (s: Sort) => `${s.field}:${s.descending ? "desc" : "asc"}`;

export function SortSelect() {
  const { sort, setSort } = useQueryState();
  const current = keyOf(sort);
  const known = OPTIONS.some((o) => keyOf(o.sort) === current);

  const onChange = (value: string) => {
    const found = OPTIONS.find((o) => keyOf(o.sort) === value);
    if (found) setSort(found.sort);
  };

  return (
    <label className="sort-select">
      <IconSort className="sort-select__icon" aria-hidden="true" />
      <span className="visually-hidden">Сортировка</span>
      <select
        className="sort-select__control"
        value={known ? current : "custom"}
        onChange={(e) => onChange(e.target.value)}
      >
        {!known ? (
          <option value="custom" disabled>
            Своя сортировка (по столбцу)
          </option>
        ) : null}
        {OPTIONS.map((o) => (
          <option key={keyOf(o.sort)} value={keyOf(o.sort)}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
