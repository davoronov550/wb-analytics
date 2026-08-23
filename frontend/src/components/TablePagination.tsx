import { IconChevron, IconChevronsLeft, IconChevronsRight } from "./ui/icons";

export const PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const;

interface Props {
  pageIndex: number;
  pageCount: number;
  pageSize: number;
  /** Rows currently loaded into the table (the paginated-over set). */
  loadedRows: number;
  /** Total matching rows on the server (may exceed loadedRows at the cap). */
  totalRows?: number;
  onFirst: () => void;
  onPrev: () => void;
  onNext: () => void;
  onLast: () => void;
  onPageSize: (size: number) => void;
}

export function TablePagination({
  pageIndex,
  pageCount,
  pageSize,
  loadedRows,
  totalRows,
  onFirst,
  onPrev,
  onNext,
  onLast,
  onPageSize,
}: Props) {
  const canPrev = pageIndex > 0;
  const canNext = pageIndex < pageCount - 1;
  const start = loadedRows === 0 ? 0 : pageIndex * pageSize + 1;
  const end = Math.min((pageIndex + 1) * pageSize, loadedRows);
  const capped = totalRows != null && totalRows > loadedRows;

  return (
    <div className="pagination">
      <label className="pagination__size">
        <span className="pagination__size-label">На странице</span>
        <select
          className="pagination__size-select"
          value={pageSize}
          onChange={(e) => onPageSize(Number(e.target.value))}
        >
          {PAGE_SIZE_OPTIONS.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>

      <span className="pagination__range">
        {start}–{end} из {loadedRows}
        {capped ? <span className="pagination__cap"> (первые {loadedRows} из {totalRows})</span> : null}
      </span>

      <div className="pagination__nav">
        <button
          type="button"
          className="pagination__btn"
          onClick={onFirst}
          disabled={!canPrev}
          aria-label="Первая страница"
        >
          <IconChevronsLeft />
        </button>
        <button
          type="button"
          className="pagination__btn"
          onClick={onPrev}
          disabled={!canPrev}
          aria-label="Предыдущая страница"
        >
          <IconChevron className="pagination__chevron-left" />
        </button>
        <span className="pagination__page">
          {pageCount === 0 ? 0 : pageIndex + 1} / {pageCount}
        </span>
        <button
          type="button"
          className="pagination__btn"
          onClick={onNext}
          disabled={!canNext}
          aria-label="Следующая страница"
        >
          <IconChevron />
        </button>
        <button
          type="button"
          className="pagination__btn"
          onClick={onLast}
          disabled={!canNext}
          aria-label="Последняя страница"
        >
          <IconChevronsRight />
        </button>
      </div>
    </div>
  );
}
