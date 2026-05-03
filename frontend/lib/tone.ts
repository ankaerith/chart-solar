// Shared tone palette for status-keyed UI. Maps the three tones used
// by VerdictBanner (good/warn/bad) and CaveatsBlock (KNOWN/PARTIAL/
// UNKNOWN) onto Tailwind utility classes. Keeps the palette in one
// place so a token swap doesn't drift between consumers.

export type Tone = "good" | "warn" | "bad";

const TEXT: Record<Tone, string> = {
  good: "text-good",
  warn: "text-warn",
  bad: "text-bad",
};

const BG: Record<Tone, string> = {
  good: "bg-good",
  warn: "bg-warn",
  bad: "bg-bad",
};

const BORDER: Record<Tone, string> = {
  good: "border-good",
  warn: "border-warn",
  bad: "border-bad",
};

export function toneText(tone: Tone): string {
  return TEXT[tone];
}

export function toneBg(tone: Tone): string {
  return BG[tone];
}

export function toneBorder(tone: Tone): string {
  return BORDER[tone];
}
