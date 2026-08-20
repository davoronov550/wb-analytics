interface Props {
  value: number | undefined;
  onChange: (value: number | undefined) => void;
}

export function ReviewsFilter({ value, onChange }: Props) {
  return (
    <label className="filter filter--reviews">
      Мин. отзывов:
      <input
        type="number"
        min={0}
        step={10}
        value={value ?? ""}
        placeholder="0"
        onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
      />
    </label>
  );
}
