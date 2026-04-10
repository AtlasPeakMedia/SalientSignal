import { DEVIATION_COLORS, DEVIATION_LABELS } from "@/lib/colors";

const ORDER: Array<keyof typeof DEVIATION_COLORS> = [
  "deepBlue",
  "steelBlue",
  "coolGray",
  "neutral",
  "amber",
  "orange",
  "red",
];

export default function ColorLegend() {
  return (
    <div className="inline-flex items-center gap-3 text-xs text-text-secondary">
      <span className="text-mono uppercase tracking-wider">Quiet</span>
      <div className="flex">
        {ORDER.map((level) => (
          <div
            key={level}
            title={DEVIATION_LABELS[level]}
            className="w-6 h-3 first:rounded-l-sm last:rounded-r-sm"
            style={{ backgroundColor: DEVIATION_COLORS[level] }}
          />
        ))}
      </div>
      <span className="text-mono uppercase tracking-wider">Surge</span>
    </div>
  );
}
