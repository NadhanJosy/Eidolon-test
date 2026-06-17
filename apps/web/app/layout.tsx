import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Eidolon",
  description: "Private text-only companion"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

