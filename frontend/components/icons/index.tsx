// Curated icon vocabulary.
//
// Convention:
//   • Wordmark + Arrow are bespoke (sun-rays + chevron) — branded marks.
//   • Everything else uses lucide-react with editorial defaults
//     (1.5 px stroke, lucide's default round caps).
//
// Pin a small vocabulary so the app feels consistent — don't reach into
// lucide directly from screens; import from here. Adding to the set is
// fine but should be deliberate (a UI need, not a one-off impulse).
//
// Stroke-width 1.5 matches the editorial weight in
// design/solar-decisions/project (the bespoke Wordmark uses stroke 1.6,
// the Arrow uses 1.6 — within rounding of 1.5; lucide's default is 2).

import { forwardRef } from "react";
import type { LucideIcon, LucideProps } from "lucide-react";
import {
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CircleAlert,
  ExternalLink,
  Info,
  Lock,
  Menu,
  Search,
  TriangleAlert,
  Upload,
  X,
} from "lucide-react";

export { Arrow } from "../ui/arrow";
export { Wordmark } from "../ui/wordmark";

// Wrap each lucide icon so the editorial defaults (strokeWidth 1.5) apply
// without every call site re-passing them. Callers can still override.
function withDefaults(Icon: LucideIcon, displayName: string) {
  const Wrapped = forwardRef<SVGSVGElement, LucideProps>(function Wrapped(
    { strokeWidth = 1.5, size = 16, ...rest },
    ref,
  ) {
    return <Icon ref={ref} strokeWidth={strokeWidth} size={size} {...rest} />;
  });
  Wrapped.displayName = displayName;
  return Wrapped;
}

export const Icon = {
  Check: withDefaults(Check, "Icon.Check"),
  ChevronDown: withDefaults(ChevronDown, "Icon.ChevronDown"),
  ChevronLeft: withDefaults(ChevronLeft, "Icon.ChevronLeft"),
  ChevronRight: withDefaults(ChevronRight, "Icon.ChevronRight"),
  ChevronUp: withDefaults(ChevronUp, "Icon.ChevronUp"),
  Close: withDefaults(X, "Icon.Close"),
  ExternalLink: withDefaults(ExternalLink, "Icon.ExternalLink"),
  Info: withDefaults(Info, "Icon.Info"),
  Lock: withDefaults(Lock, "Icon.Lock"),
  Menu: withDefaults(Menu, "Icon.Menu"),
  Search: withDefaults(Search, "Icon.Search"),
  Warn: withDefaults(TriangleAlert, "Icon.Warn"),
  Alert: withDefaults(CircleAlert, "Icon.Alert"),
  Upload: withDefaults(Upload, "Icon.Upload"),
};
