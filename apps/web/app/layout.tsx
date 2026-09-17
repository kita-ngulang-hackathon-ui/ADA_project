// Root layout: nav, tenant switcher, synthetic-data banner.
// TODO: implement (see apps/web/README.md).
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
