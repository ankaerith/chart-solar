import type { ReactNode } from "react";

// DetectRow — label/value pair used inside the right-hand preview Panel
// on every wizard step. Dashed underline rule between rows; mono-set
// values to keep numerics aligned. Mirrors
// design/solar-decisions/project/screen-wizard.jsx:DetectRow (122–132).

export function DetectRow({
  label,
  value,
  sub,
}: {
  label: ReactNode;
  value: ReactNode;
  sub?: ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-dashed border-rule pb-2">
      <span className="text-[12px] text-ink-dim">{label}</span>
      <div className="text-right">
        <div className="font-mono text-[12px] font-medium text-ink">
          {value}
        </div>
        {sub && (
          <div className="font-mono text-[10px] text-ink-faint">{sub}</div>
        )}
      </div>
    </div>
  );
}
