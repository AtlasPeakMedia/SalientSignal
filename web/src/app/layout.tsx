import type { Metadata } from "next";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "SalientSignal — Foreign Media Intelligence",
  description:
    "Monitor state-run media from 151+ countries. See what regimes tell their own population versus the world. Globe-based visualization with baseline deviation tracking.",
  openGraph: {
    title: "SalientSignal — Foreign Media Intelligence",
    description:
      "Monitor state-run media from 151+ countries. See domestic vs. international messaging side-by-side.",
    type: "website",
  },
  robots: {
    index: false, // Pre-launch — disable until JAG sign-off
    follow: false,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-bg-base text-text-body min-h-screen relative">
        <div className="grain-overlay" aria-hidden="true" />
        <div className="relative z-10">{children}</div>
      </body>
    </html>
  );
}
