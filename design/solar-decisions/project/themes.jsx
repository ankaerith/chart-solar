// Solar Decisions — locked theme: Solstice · Ink.
// Architectural editorial direction. Cool oyster paper, prussian-blue ink, oxblood secondary.
// Newsreader serif headlines, Inter body, IBM Plex Mono for numerics.

const SD_THEME_VARS = {
  '--bg': '#ecebe3',
  '--bg-2': '#dfdecf',
  '--panel': '#f7f5ec',
  '--panel-2': '#e8e6d6',
  '--ink': '#0f1421',
  '--ink-2': '#1f2a3f',
  '--ink-dim': '#566173',
  '--ink-faint': '#8a92a0',
  '--rule': '#c4bfac',
  '--rule-strong': '#0f1421',
  '--accent': '#1d3461',          // prussian-blue ink
  '--accent-ink': '#f7f5ec',
  '--accent-2': '#7a2826',         // oxblood
  '--good': '#2e6b48',
  '--warn': '#a86512',
  '--bad': '#7a2826',
  '--display-font': "'Newsreader', 'Source Serif 4', Georgia, serif",
  '--body-font': "'Inter', system-ui, sans-serif",
  '--mono-font': "'IBM Plex Mono', ui-monospace, monospace",
  '--display-weight': '600',
  '--display-tracking': '-0.022em',
  '--radius': '6px',
  '--radius-lg': '10px',
};

function applyTheme() {
  const root = document.documentElement;
  Object.entries(SD_THEME_VARS).forEach(([k, v]) => root.style.setProperty(k, v));
}

window.applyTheme = applyTheme;
window.SD_THEME_VARS = SD_THEME_VARS;
