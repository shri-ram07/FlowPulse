import type { Metadata, Viewport } from "next";
import Link from "next/link";
import AccessibleModeToggle from "@/components/AccessibleModeToggle";
import NavLinks from "@/components/NavLinks";
import { ToastProvider } from "@/components/Toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "FlowPulse — Stadium Crowd Orchestration",
  description: "Sense. Decide. Influence. Optimize. AI-powered crowd flow for live venues.",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  themeColor: "#0284c7",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a href="#main" className="skip-link">
          Skip to main content
        </a>
        <nav className="nav" aria-label="Primary">
          <Link href="/" className="brand" aria-label="FlowPulse home">
            <span className="brand-dot" aria-hidden />
            FlowPulse
          </Link>
          <span className="tagline" aria-hidden>
            Sense · Decide · Influence · Optimize
          </span>
          <div className="spacer" />
          <NavLinks />
          <AccessibleModeToggle />
        </nav>
        <ToastProvider>
          <div id="main">{children}</div>
        </ToastProvider>
      </body>
    </html>
  );
}
