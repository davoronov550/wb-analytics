import Slider from "rc-slider";
import "rc-slider/assets/index.css";

interface Props {
  min: number;
  max: number;
  value: [number, number];
  onChange: (value: [number, number]) => void;
}

export function PriceRangeSlider({ min, max, value, onChange }: Props) {
  return (
    <div className="filter filter--price">
      <label>
        Цена: {value[0]} — {value[1]} ₽
      </label>
      <Slider
        range
        min={min}
        max={max}
        value={value}
        onChange={(next) => onChange(next as [number, number])}
      />
    </div>
  );
}
