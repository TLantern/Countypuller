import type { Metadata } from "next";
import { Geist, Geist_Mono, Faustina } from "next/font/google";
import "./globals.css";
import NextAuthSessionProvider from "@/components/session-provider";
import { ThemeProvider, useTheme } from "@/context/ThemeContext";
import { FeedbackProvider } from "@/context/FeedbackContext";
import React from "react";
import ThemeToggle from "@/components/ThemeToggle";
import ChatbotWidget from "@/components/ChatbotWidget";
import ClientOnlyToggles from "@/components/ClientOnlyToggles";


const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

const faustina = Faustina({
  variable: "--font-faustina",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  style: ["normal", "italic"],
  display: "swap",
  preload: true,
});

export const metadata: Metadata = {
  title: "Clerk Crawler",
  description: "Clerk Crawler - Instantly search and analyze property records across 200+ counties.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link
          rel="preload"
          href="https://fonts.googleapis.com/css2?family=Faustina:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,300;1,400;1,500;1,600;1,700;1,800&display=swap"
          as="style"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Faustina:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,300;1,400;1,500;1,600;1,700;1,800&display=swap"
        />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${faustina.variable} antialiased`}
      >
        <ThemeProvider>
          <FeedbackProvider>
            <NextAuthSessionProvider>
              <ClientOnlyToggles />
              {children}
            </NextAuthSessionProvider>
          </FeedbackProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
