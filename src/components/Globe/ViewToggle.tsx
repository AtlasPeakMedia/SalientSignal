"use client";

type ViewMode = "DOMESTIC" | "INTERNATIONAL" | "BOTH";

interface Props {
  value: ViewMode;
  onChange: (v: ViewMode) => void;
}

const OPTIONS: { value: ViewMode; label: string }[] = [
  { value: "DOMESTIC", label: "Domestic" },
  { value: "INTERNATIONAL", label: "International" },
  { value: "BOTH", label: "Both" },
];

export default function ViewToggle({ value, onChange }: Props) {
  return (
    <div className="inline-flex rounded-full border border-bg-divider bg-bg-card p-1">
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`px-4 py-1.5 text-xs font-medium rounded-full transition-colors ${
            value === opt.value
              ? "bg-accent-teal text-white"
              : "text-text-secondary hover:text-text-body"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
