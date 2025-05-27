import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import NextAuthSessionProvider from "@/components/session-provider";
import { ThemeProvider, useTheme } from "@/context/ThemeContext";
import React from "react";
import ThemeToggle from "@/components/ThemeToggle";
import ChatbotWidget from "@/components/ChatbotWidget";
import ClientOnlyToggles from "@/components/ClientOnlyToggles";


const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
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
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ThemeProvider>
          <ClientOnlyToggles />
          <NextAuthSessionProvider>
            {children}
          </NextAuthSessionProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
