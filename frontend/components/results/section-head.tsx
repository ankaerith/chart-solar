import type { ReactNode } from "react";
import { MonoLabel } from "@/components/ui";

// design ref · screen-results.jsx:SectionHead (77–94)

export function SectionHead({
  kicker,
  title,
  right,
}: {
  kicker: string;
  title: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4 border-b border-rule-strong pb-3">
      <div>
        <MonoLabel>{kicker}</MonoLabel>
        <h3 className="mt-1.5 text-[26px] leading-[1.1] font-display">
          {title}
        </h3>
      </div>
      {right}
    </div>
  );
}
