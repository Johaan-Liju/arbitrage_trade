import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "GoldLens | Gold, in context.", description: "Local-first synthetic gold contract research." };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" className="dark"><body>{children}</body></html>;
}
