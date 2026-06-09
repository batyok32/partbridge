import { Inter, IBM_Plex_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";

import { Providers } from "./providers";
import { Navbar } from "@/components/Navbar";
import { themeBootstrapScript } from "@/components/ThemeScript";

const inter = Inter({
  variable: "--ff-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--ff-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata = {
  title: "LookMyPart — buy and sell used car parts simply",
  description:
    "The used car parts marketplace. Sell your car's parts with real market pricing. Find the exact part you need with verified condition and transparent shipping.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body
        className={`${ibmPlexMono.variable} min-h-screen antialiased`}
        style={{
          fontFamily: "var(--font-body)",
          background: "var(--bg-base)",
          color: "var(--text-primary)",
        }}
      >
        <Script
          id="partbridge-theme"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{ __html: themeBootstrapScript() }}
        />
        <Providers>
          <Navbar />
          {children}
        </Providers>
      </body>
    </html>
  );
}
