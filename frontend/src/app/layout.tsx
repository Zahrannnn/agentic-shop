import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import Script from "next/script";
import type { ReactNode } from "react";
import "./globals.css";
import { Providers } from "./providers";
import { env } from "@/shared/config/env";

// The Curator's Desk editorial faces (DESIGN.md §3), exposed as the exact CSS
// variables globals.css consumes for --font-sans / --font-mono.
const editorialSans = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-editorial-sans",
});

const editorialMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-editorial-mono",
});

export const metadata: Metadata = {
  metadataBase: new URL(env.NEXT_PUBLIC_APP_URL),
  title: {
    default: env.NEXT_PUBLIC_APP_NAME,
    template: `%s | ${env.NEXT_PUBLIC_APP_NAME}`,
  },
  description:
    "Agentic shopping: chat with an agent that searches, compares, and recommends — rendered as generated UI plans.",
  openGraph: {
    title: env.NEXT_PUBLIC_APP_NAME,
    description:
      "A feature-first Next.js starter for CORELIA product applications.",
    type: "website",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${editorialSans.variable} ${editorialMono.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <Script src="/runtime-env.js" strategy="beforeInteractive" />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
