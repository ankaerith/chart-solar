// Fixed-position concentric-rings + sun motif — pinned to the viewport
// behind page content. Used on marketing routes only.
//
// Faithful to design/solar-decisions/project/screen-landing.jsx:62–86
// (the design uses a portal to body to escape stacking context; in a
// Next.js layout we render in place with z-0 so all subsequent content
// uses z-10+ to layer over).

export function SunBackdrop() {
  const cx = 1100;
  const cy = 140;
  const sunR = 70;
  const rings = [140, 220, 320, 440, 580, 740, 920];

  return (
    <svg
      viewBox="0 0 1280 900"
      preserveAspectRatio="xMaxYMin slice"
      aria-hidden="true"
      className="pointer-events-none fixed top-0 right-0 z-0 h-screen w-screen"
    >
      <g fill="none" stroke="var(--accent)" strokeWidth={1}>
        {rings.map((r, i) => (
          <circle
            key={r}
            cx={cx}
            cy={cy}
            r={r}
            opacity={Math.max(0, 0.18 - i * 0.018)}
          />
        ))}
      </g>
      <circle cx={cx} cy={cy} r={sunR} fill="var(--accent)" opacity={0.85} />
    </svg>
  );
}
