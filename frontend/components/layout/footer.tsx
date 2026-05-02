import Link from "next/link";
import { Wordmark } from "@/components/icons";

const COLS = [
  {
    head: "Product",
    items: [
      ["Forecast", "/forecast"],
      ["Audit a proposal", "/audit"],
      ["Pricing", "/pricing"],
      ["How it works", "/methodology"],
    ],
  },
  {
    head: "Resources",
    items: [
      ["Field Notes", "/notes"],
      ["Methodology", "/methodology"],
      ["Sources & data", "/methodology/sources"],
      ["Changelog", "/changelog"],
    ],
  },
  {
    head: "Company",
    items: [
      ["About", "/about"],
      ["Independence pledge", "/about/independence"],
      ["Press", "/press"],
      ["Contact", "/contact"],
    ],
  },
  {
    head: "Legal",
    items: [
      ["Privacy", "/legal/privacy"],
      ["Terms", "/legal/terms"],
      ["Security", "/legal/security"],
      ["Disclosures", "/legal/disclosures"],
    ],
  },
] as const;

const VERSION = "v0.1.0";
const ENGINE_PIN = "engine pinned 2026.04";

export function Footer() {
  return (
    <footer className="mt-10 border-t border-rule bg-panel-2 px-10 pt-14 pb-8">
      <div className="mx-auto max-w-[1280px]">
        <div className="mb-12 grid gap-10 [grid-template-columns:minmax(0,1.4fr)_repeat(4,minmax(0,1fr))]">
          <div>
            <Wordmark />
            <p className="mt-3.5 max-w-[280px] text-[13px] leading-[1.55] text-ink-2">
              Independent solar math. No installer affiliations, no lead-gen,
              no kickbacks. We work for the homeowner.
            </p>
          </div>
          {COLS.map((col) => (
            <div key={col.head}>
              <div className="mb-3.5 font-mono text-[10.5px] tracking-[0.14em] text-ink-faint uppercase">
                {col.head}
              </div>
              <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
                {col.items.map(([label, href]) => (
                  <li key={label}>
                    <Link
                      href={href}
                      className="text-left text-[13px] text-ink-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-5 font-mono text-[11px] tracking-[0.04em] text-ink-faint">
          <div>
            © {new Date().getFullYear()} Chart Solar · independent forecasting
            for residential solar
          </div>
          <div className="flex gap-[18px]">
            <span>
              {VERSION} · {ENGINE_PIN}
            </span>
            <span>
              status: <span className="text-good">● operational</span>
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
