interface Props {
  value: number | undefined;
  onChange: (value: number | undefined) => void;
}

const OPTIONS = [3, 3.5, 4, 4.5];

export function RatingFilter({ value, onChange }: Props) {
  return (
    <label className="filter filter--rating">
      Мин. рейтинг:
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
      >
        <option value="">любой</option>
        {OPTIONS.map((option) => (
          <option key={option} value={option}>
            от {option}
          </option>
        ))}
      </select>
    </label>
  );
}
