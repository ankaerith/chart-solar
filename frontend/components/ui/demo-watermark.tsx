// Diagonal "DEMO DATA" watermark band — overlays preview content unmissably.
// Place inside a `relative` parent (Modal, Panel) to anchor the absolute fill.

export function DemoWatermark() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 overflow-hidden rounded-[inherit]"
    >
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 -rotate-[18deg] whitespace-nowrap font-mono font-bold tracking-[0.18em] text-accent opacity-[0.07]"
        style={{ fontSize: "clamp(48px, 9vw, 110px)" }}
      >
        DEMO · DEMO · DEMO
      </div>
    </div>
  );
}
