import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter, Newsreader, Source_Serif_4 } from "next/font/google";
import "./globals.css";

const newsreader = Newsreader({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-display",
  weight: ["500", "600", "700"],
  style: ["normal", "italic"],
});

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-body",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-mono",
  weight: ["400", "500", "600"],
});

const sourceSerif = Source_Serif_4({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-display-fallback",
});

export const metadata: Metadata = {
  title: "Chart Solar",
  description: "Plan it. Check it. Track it. — the honest math for your roof.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      data-theme="solstice-ink"
      className={`${newsreader.variable} ${inter.variable} ${ibmPlexMono.variable} ${sourceSerif.variable}`}
    >
      <body className="min-h-screen bg-bg text-ink antialiased">{children}</body>
    </html>
  );
}
