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
          <a href="/pricing" style={{ color: "#fff", textDecoration: "none" }}>Pricing</a>
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
            <Link href="/pricing">
              <Button asChild size="lg" className="glow-pulse-btn" style={{ background: "#fff", color: "#000", width: isMobile ? "100%" : undefined, marginBottom: isMobile ? 8 : 0, position: 'relative', zIndex: 1 }}>
                <span style={{ color: "#000", position: 'relative', zIndex: 2 }}>Get Started</span>
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
        {/* Clerk Crawler Demo Video to the right of hero text */}
        <div style={{ width: isMobile ? '100%' : 540, maxWidth: '100%', margin: isMobile ? '2rem auto 0 auto' : '0', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <h3 style={{
            color: '#fff',
            fontWeight: 800,
            fontFamily: 'Inter, sans-serif',
            fontSize: isMobile ? '1.7rem' : '2.8rem',
            marginBottom: 18,
            textAlign: 'center',
            textShadow: '0 0 12px #3b82f6',
            lineHeight: 1.1,
          }}>
            Clerk Crawler Demo
          </h3>
          <div style={{ borderRadius: 32, boxShadow: '0 0 56px 16px #3b82f6, 0 0 0 8px #fff2', background: 'rgba(59,130,246,0.15)', padding: 20, width: '100%' }}>
            <div style={{ position: 'relative', paddingBottom: '56.25%', height: 0 }}>
              <iframe src="https://www.loom.com/embed/e1a6688e0d654818b61464c71fe98c00?sid=45ff9108-8af0-4762-b6cf-ce30af5d337e" frameBorder="0" allowFullScreen style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', borderRadius: 24 }}></iframe>
            </div>
          </div>
        </div>
      </main>
      {/* Our Mission section centered below hero+demo */}
      <section style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', margin: isMobile ? '2.5rem 0 0 0' : '3.5rem 0 0 0' }}>
        <h3 style={{
          color: '#fff',
          fontWeight: 800,
          fontFamily: 'Inter, sans-serif',
          fontSize: isMobile ? '1.7rem' : '2.8rem',
          marginBottom: 18,
          textAlign: 'center',
          textShadow: '0 0 12px #3b82f6',
          lineHeight: 1.1,
        }}>
          Our Mission
        </h3>
        <div style={{ borderRadius: 32, boxShadow: '0 0 56px 16px #3b82f6, 0 0 0 8px #fff2', background: 'rgba(59,130,246,0.15)', padding: 20, width: isMobile ? '99%' : 540, maxWidth: '100%' }}>
          <div style={{ position: 'relative', paddingBottom: '56.25%', height: 0 }}>
            <iframe src="https://www.loom.com/embed/662a5f2f4b224dff9e1bab82085efb84?sid=ca2107ad-a492-4c04-b5ec-f68c1db06055" frameBorder="0" allowFullScreen style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', borderRadius: 24 }}></iframe>
          </div>
        </div>
      </section>
      <style jsx global>{`
        .home-shadow-btn:hover {
          box-shadow: 0 8px 32px 0 rgba(224,224,224,0.4) !important;
        }
        .glow-pulse-btn {
          box-shadow: 0 0 32px 0 #3b82f6, 0 0 0 0 #3b82f6;
          animation: glow-pulse 3s ease-in-out infinite;
          transition: box-shadow 0.3s;
        }
        @keyframes glow-pulse {
          0% {
            box-shadow: 0 0 32px 0 #3b82f6, 0 0 0 0 #3b82f6;
          }
          50% {
            box-shadow: 0 0 48px 12px #3b82f6, 0 0 0 8px #3b82f6;
          }
          100% {
            box-shadow: 0 0 32px 0 #3b82f6, 0 0 0 0 #3b82f6;
          }
        }
      `}</style>
    </div>
  );
}
