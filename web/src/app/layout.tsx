import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

import { ThemeProvider } from "@/components/providers/theme-provider";
import ToastProvider from "@/components/providers/ToastProvider";
import { SessionProvider } from "@/providers/session-provider";
import ReactQueryProvider from "@/components/providers/ReactQueryProvider";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Enterprise AI Workspace (AMOF Edition)",
  description: "Unified AI-native enterprise workspace powered by AMOF.",
  applicationName: "Enterprise AI Workspace",
  keywords: [
    "AI",
    "Enterprise",
    "Workspace",
    "AMOF",
    "LLM",
    "Productivity",
  ],
  authors: [
    {
      name: "Suyash Sahu",
    },
  ],
};

export const viewport: Viewport = {
  themeColor: "#4F46E5",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${inter.variable} ${jetbrainsMono.variable} antialiased`}
      >
        <ThemeProvider>
          <ReactQueryProvider>
            <SessionProvider>
              <ToastProvider />
              {children}
            </SessionProvider>
          </ReactQueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
