import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";

export const metadata: Metadata = {
  title: "Wiqaya – precision prevention and screening",
  description: "Population prioritisation prototype for preventive care in Abu Dhabi. Simulated cohort.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans">
        <a href="#main" className="sr-only bg-white p-2 focus:not-sr-only focus:absolute focus:left-2 focus:top-2">
          Skip to content
        </a>
        <Header />
        <main id="main" className="mx-auto max-w-7xl px-4 pb-16 pt-6">
          {children}
        </main>
        <footer className="border-t border-line py-6 text-center text-xs text-muted">
          Wiqaya prototype · every record is synthetic (<span className="font-semibold">Simulated cohort</span>) ·{" "}
          <a className="underline" href="/about">
            Assumptions &amp; limitations
          </a>{" "}
          ·{" "}
          <a className="underline" href="/admin?tab=provenance">
            Data provenance
          </a>{" "}
          · Map data ©{" "}
          <a className="underline" href="https://www.openstreetmap.org/copyright">
            OpenStreetMap contributors
          </a>
        </footer>
      </body>
    </html>
  );
}
