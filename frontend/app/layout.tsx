import type { Metadata } from "next";
import { Geist_Mono, Geist } from "next/font/google";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

const geistSans = Geist({
  subsets: ["latin"],
  variable: "--font-geist-sans",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
});

export const metadata: Metadata = {
  title: "LiveBroker",
  description: "Natural language strategy compiler for paper trading.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        <div className="mx-auto min-h-screen max-w-7xl px-6 py-8 sm:px-10">
          <header className="mb-10 flex flex-col gap-5 border-b border-black/10 pb-6 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <Link className="text-3xl font-semibold tracking-tight text-ink" href="/">
                LiveBroker
              </Link>
              <p className="mt-2 max-w-2xl text-sm text-black/65">
                Backend-driven strategy validation, compilation, and backtesting.
              </p>
            </div>
            <nav className="flex gap-4 text-sm font-medium">
              <Link href="/strategy/new">New Strategy</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
