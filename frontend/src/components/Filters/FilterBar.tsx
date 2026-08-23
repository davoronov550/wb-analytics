import { useQueryState } from "../../context/QueryContext";
import { PriceRangeSlider } from "./PriceRangeSlider";
import { RatingFilter } from "./RatingFilter";
import { ReviewsFilter } from "./ReviewsFilter";
import "./FilterBar.css";

const PRICE_MIN = 0;
const PRICE_MAX = 100000;

export function FilterBar() {
  const { filters, patchFilters } = useQueryState();
  const priceValue: [number, number] = [
    filters.minPrice ?? PRICE_MIN,
    filters.maxPrice ?? PRICE_MAX,
  ];

  const hasFilters =
    filters.minPrice != null ||
    filters.maxPrice != null ||
    filters.minRating != null ||
    filters.minReviews != null;

  return (
    <div className="filter-bar">
      <div className="filter-bar__control filter-bar__control--price">
        <PriceRangeSlider
          min={PRICE_MIN}
          max={PRICE_MAX}
          value={priceValue}
          onChange={([lo, hi]) => patchFilters({ minPrice: lo, maxPrice: hi })}
        />
      </div>
      <div className="filter-bar__control">
        <RatingFilter value={filters.minRating} onChange={(v) => patchFilters({ minRating: v })} />
      </div>
      <div className="filter-bar__control">
        <ReviewsFilter value={filters.minReviews} onChange={(v) => patchFilters({ minReviews: v })} />
      </div>
      {hasFilters ? (
        <button
          type="button"
          className="btn btn--subtle btn--sm filter-bar__reset"
          onClick={() =>
            patchFilters({
              minPrice: undefined,
              maxPrice: undefined,
              minRating: undefined,
              minReviews: undefined,
            })
          }
        >
          Сбросить фильтры
        </button>
      ) : null}
    </div>
  );
}
