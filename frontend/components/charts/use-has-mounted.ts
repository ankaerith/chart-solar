"use client";

import { useSyncExternalStore } from "react";

// Recharts' ResponsiveContainer measures its parent via ResizeObserver. Both
// the SSR pass and the very-first client render lack measurable dimensions,
// which makes Recharts log `width(-1) and height(-1)` warnings. Gate the
// chart behind a "client-only" flag so it only renders once layout exists —
// the wrapper div keeps its `height` so this is layout-stable.
//
// Uses useSyncExternalStore (React 19's documented "am I on the client"
// pattern) instead of useEffect+setState — it satisfies
// react-hooks/set-state-in-effect.
const subscribe = () => () => {};

export function useHasMounted(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}
