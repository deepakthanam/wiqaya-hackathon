import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";

const siteUrl =
  process.env.SITE_URL ??
  (process.env.VERCEL_PROJECT_PRODUCTION_URL ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : "http://localhost:3000");
const title = "Wiqaya – precision prevention and screening";
const description = "Population prioritisation prototype for preventive care in Abu Dhabi. Simulated cohort.";

// icon.png, apple-icon.png and opengraph-image.png in this folder are picked up by Next.js automatically.
export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title,
  description,
  openGraph: { title, description, siteName: "Wiqaya", type: "website" },
  twitter: { card: "summary_large_image", title, description },
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
