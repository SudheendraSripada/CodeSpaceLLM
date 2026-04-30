import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Assistant Foundation",
  description: "A Claude-like assistant foundation with persistent chat and admin settings."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

