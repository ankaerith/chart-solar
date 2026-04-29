import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Chart Solar",
  description: "Plan it. Check it. Track it. — the honest math for your roof.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-foreground antialiased">{children}</body>
    </html>
  );
}
