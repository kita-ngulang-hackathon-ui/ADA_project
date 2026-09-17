// Root layout: font, global styles. The app shell (top bar + collapsible
// sidebar) lives in app/(console)/layout.tsx so /login can render standalone.
import type { Metadata } from "next";
import { Lato } from "next/font/google";
import "./globals.css";

// next/font self-hosts the files at build time, so nothing is fetched from
// Google at runtime (offline demo rule in apps/web/README.md).
const lato = Lato({
  subsets: ["latin"],
  weight: ["300", "400", "700", "900"],
  display: "swap",
  variable: "--font-lato",
});

export const metadata: Metadata = {
  title: "ADA Solutions",
  description: "Ops console for the ADA retention engine.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={lato.variable}>
      <body>{children}</body>
    </html>
  );
}
