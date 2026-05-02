// Default fallback for the @modal parallel-route slot. Returns null
// so the marketing surface renders without a modal overlay until a
// matching `@modal/(.)<route>/page.tsx` intercepts a navigation.

export default function ModalSlotDefault() {
  return null;
}
