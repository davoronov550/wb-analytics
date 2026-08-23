import { useState, type ReactNode } from "react";

import { useQueryState } from "../../context/QueryContext";
import { IconChevron } from "../ui/icons";
import { PriceRangeSlider } from "./PriceRangeSlider";
import "./FilterRail.css";

const PRICE_MIN = 0;
const PRICE_MAX = 100000;

interface SectionProps {
  title: string;
  active: number;
  defaultOpen?: boolean;
  children: ReactNode;
}

function Section({ title, active, defaultOpen = false, children }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`rail-section${open ? " is-open" : ""}`}>
      <button
        type="button"
        className="rail-section__head"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="rail-section__title">
          {title}
          {active > 0 ? <span className="rail-section__dot" aria-hidden="true" /> : null}
        </span>
        <IconChevron className="rail-section__chevron" />
      </button>
      {open ? <div className="rail-section__body">{children}</div> : null}
    </div>
  );
}

interface NumberFieldProps {
  label: string;
  value: number | undefined;
  onChange: (v: number | undefined) => void;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
}

function NumberField({ label, value, onChange, min, max, step, placeholder }: NumberFieldProps) {
  return (
    <label className="rail-field">
      <span className="rail-field__label">{label}</span>
      <input
        className="input rail-field__input"
        type="number"
        inputMode="decimal"
        value={value ?? ""}
        min={min}
        max={max}
        step={step}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
      />
    </label>
  );
}

export function FilterRail() {
  const { filters, patchFilters } = useQueryState();

  const priceActive = (filters.minPrice != null ? 1 : 0) + (filters.maxPrice != null ? 1 : 0);
  const ratingActive = (filters.minRating != null ? 1 : 0) + (filters.maxRating != null ? 1 : 0);
  const reviewsActive = (filters.minReviews != null ? 1 : 0) + (filters.maxReviews != null ? 1 : 0);
  const total = priceActive + ratingActive + reviewsActive;

  const priceValue: [number, number] = [
    filters.minPrice ?? PRICE_MIN,
    filters.maxPrice ?? PRICE_MAX,
  ];

  const reset = () =>
    patchFilters({
      minPrice: undefined,
      maxPrice: undefined,
      minRating: undefined,
      maxRating: undefined,
      minReviews: undefined,
      maxReviews: undefined,
    });

  return (
    <div className="filter-rail">
      <div className="filter-rail__head">
        <span className="filter-rail__title">
          Фильтры
          {total > 0 ? <span className="badge badge--accent">{total}</span> : null}
        </span>
        {total > 0 ? (
          <button type="button" className="filter-rail__reset" onClick={reset}>
            Сбросить
          </button>
        ) : null}
      </div>

      <div className="filter-rail__sections">
        <Section title="Цена (со скидкой)" active={priceActive} defaultOpen>
          <PriceRangeSlider
            min={PRICE_MIN}
            max={PRICE_MAX}
            value={priceValue}
            onChange={([lo, hi]) =>
              patchFilters({
                minPrice: lo > PRICE_MIN ? lo : undefined,
                maxPrice: hi < PRICE_MAX ? hi : undefined,
              })
            }
          />
          <div className="rail-field-row">
            <NumberField
              label="от, ₽"
              value={filters.minPrice}
              min={0}
              placeholder="0"
              onChange={(v) => patchFilters({ minPrice: v })}
            />
            <NumberField
              label="до, ₽"
              value={filters.maxPrice}
              min={0}
              placeholder="∞"
              onChange={(v) => patchFilters({ maxPrice: v })}
            />
          </div>
        </Section>

        <Section title="Рейтинг" active={ratingActive} defaultOpen>
          <div className="rail-field-row">
            <NumberField
              label="от"
              value={filters.minRating}
              min={0}
              max={5}
              step={0.1}
              placeholder="0"
              onChange={(v) => patchFilters({ minRating: v })}
            />
            <NumberField
              label="до"
              value={filters.maxRating}
              min={0}
              max={5}
              step={0.1}
              placeholder="5"
              onChange={(v) => patchFilters({ maxRating: v })}
            />
          </div>
          <div className="rail-chips">
            {[4, 4.5].map((r) => (
              <button
                key={r}
                type="button"
                className={`rail-chip${filters.minRating === r ? " is-active" : ""}`}
                onClick={() =>
                  patchFilters({ minRating: filters.minRating === r ? undefined : r })
                }
              >
                от {r}★
              </button>
            ))}
          </div>
        </Section>

        <Section title="Отзывы" active={reviewsActive}>
          <div className="rail-field-row">
            <NumberField
              label="от"
              value={filters.minReviews}
              min={0}
              placeholder="0"
              onChange={(v) => patchFilters({ minReviews: v })}
            />
            <NumberField
              label="до"
              value={filters.maxReviews}
              min={0}
              placeholder="∞"
              onChange={(v) => patchFilters({ maxReviews: v })}
            />
          </div>
        </Section>
      </div>
    </div>
  );
}
