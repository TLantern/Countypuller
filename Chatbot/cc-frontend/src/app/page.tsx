"use client";
import React from "react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

const homeButtonShadow = {
  boxShadow: '0 4px 24px 0 rgba(224,224,224,0.6)',
  transition: 'box-shadow 0.2s',
};
const homeButtonHover = {
  boxShadow: '0 8px 32px 0 rgba(224,224,224,0.8)',
};

function useIsMobile() {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(max-width: 600px)').matches;
}

export default function Home() {
  const isMobile = typeof window !== 'undefined' && window.matchMedia('(max-width: 600px)').matches;
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #1e2a78 0%, #3a3d9f 100%)",
        color: "#fff",
        padding: "0",
        fontFamily: "Inter, sans-serif",
      }}
    >
      {/* Header */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: isMobile ? "1rem" : "2rem 4rem 1.5rem 4rem",
          flexDirection: isMobile ? "column" : "row",
          flexWrap: "wrap",
        }}
      >
        <div style={{ fontWeight: 700, fontSize: isMobile ? "1.1rem" : "1.5rem", letterSpacing: "1px", marginBottom: isMobile ? 12 : 0 }}>
          Clerk<span style={{ color: "#4fd1c5" }}> Crawler</span>
        </div>
        <nav style={{ display: "flex", gap: isMobile ? "1rem" : "2rem", alignItems: "center", flexWrap: "wrap", flexDirection: isMobile ? "column" : "row", width: isMobile ? "100%" : undefined, marginTop: isMobile ? 12 : 0 }}>
          <a href="#" style={{ color: "#fff", textDecoration: "none" }}>Home</a>
          <a href="#" style={{ color: "#fff", textDecoration: "none" }}>About us</a>
          <a href="#" style={{ color: "#fff", textDecoration: "none" }}>Pricing</a>
          <a href="#" style={{ color: "#fff", textDecoration: "none" }}>Features</a>
          <Link href="/login">
            <Button
              asChild
              style={{ marginLeft: isMobile ? 0 : "1.5rem", background: "#fff", color: "#000", width: isMobile ? "100%" : undefined, marginTop: isMobile ? 8 : 0 }}
            >
              <span style={{ color: "#000" }}>Log In</span>
            </Button>
          </Link>
        </nav>
      </header>

      {/* Hero Section */}
      <main
        style={{
          display: "flex",
          flexDirection: isMobile ? "column" : "row",
          alignItems: "center",
          justifyContent: "space-between",
          padding: isMobile ? "1.5rem" : "4rem 8vw",
          gap: "2rem",
        }}
      >
        <div style={{ maxWidth: isMobile ? "100%" : "600px", width: "100%" }}>
          <h1 style={{ fontSize: isMobile ? "1.5rem" : "2.8rem", fontWeight: 800, marginBottom: "1.5rem" }}>
            Revolutionize County Property Research
          </h1>
          <p style={{ fontSize: isMobile ? "1rem" : "1.25rem", marginBottom: "2.5rem", color: "#c3c6f1" }}>
            Instantly search and analyze property records across 200+ counties. 
            Save hours of manual work and close more deals with our powerful, automated research platform.
          </p>
          <div style={{ display: "flex", gap: isMobile ? "0.75rem" : "1.5rem", flexWrap: "wrap", flexDirection: isMobile ? "column" : "row", width: isMobile ? "100%" : undefined }}>
            <Link href="/login">
              <Button asChild size="lg" style={{ background: "#fff", color: "#000", width: isMobile ? "100%" : undefined, marginBottom: isMobile ? 8 : 0 }}>
                <span style={{ color: "#000" }}>Get Started</span>
              </Button>
            </Link>
            <Link href="/login">
              <Button
                size="lg"
                style={{ background: "#fff", color: "#000", width: isMobile ? "100%" : undefined }}
              >
                <span style={{ color: "#000" }}>Log In</span>
              </Button>
            </Link>
          </div>
        </div>
        {/* Placeholder for illustration */}
        <div style={{ minWidth: isMobile ? undefined : "220px", minHeight: isMobile ? 100 : "160px", background: "rgba(79,209,197,0.08)", borderRadius: "24px", display: "flex", alignItems: "center", justifyContent: "center", width: "100%", maxWidth: isMobile ? "100%" : "320px", marginTop: isMobile ? 24 : 0 }}>
          {/* You can replace this with an SVG or image */}
          <span style={{ color: "#4fd1c5", fontSize: isMobile ? "1rem" : "1.2rem" }}>[ Illustration Here ]</span>
        </div>
      </main>
      <style jsx global>{`
        .home-shadow-btn:hover {
          box-shadow: 0 8px 32px 0 rgba(224,224,224,0.4) !important;
        }
      `}</style>
    </div>
  );
}
