"use client";
import { Button } from "@/components/ui/button";
import Link from "next/link";

const homeButtonShadow = {
  boxShadow: '0 4px 24px 0 rgba(224,224,224,0.6)',
  transition: 'box-shadow 0.2s',
};
const homeButtonHover = {
  boxShadow: '0 8px 32px 0 rgba(224,224,224,0.8)',
};

export default function Home() {
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
          padding: "2rem 4rem 1.5rem 4rem",
        }}
      >
        <div style={{ fontWeight: 700, fontSize: "1.5rem", letterSpacing: "1px" }}>
          Clerk<span style={{ color: "#4fd1c5" }}> Crawler</span>
        </div>
        <nav style={{ display: "flex", gap: "2rem", alignItems: "center" }}>
          <a href="#" style={{ color: "#fff", textDecoration: "none" }}>Home</a>
          <a href="#" style={{ color: "#fff", textDecoration: "none" }}>About us</a>
          <a href="#" style={{ color: "#fff", textDecoration: "none" }}>Pricing</a>
          <a href="#" style={{ color: "#fff", textDecoration: "none" }}>Features</a>
          <Link href="/login">
            <Button
              asChild
              style={{ marginLeft: "1.5rem", background: "#fff", color: "#000", ...homeButtonShadow }}
              className="home-shadow-btn"
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
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "4rem 8vw",
        }}
      >
        <div style={{ maxWidth: "600px" }}>
          <h1 style={{ fontSize: "2.8rem", fontWeight: 800, marginBottom: "1.5rem" }}>
            Revolutionize County Property Research
          </h1>
          <p style={{ fontSize: "1.25rem", marginBottom: "2.5rem", color: "#c3c6f1" }}>
            Instantly search and analyze property records across 200+ counties. 
            Save hours of manual work and close more deals with our powerful, automated research platform.
          </p>
          <div style={{ display: "flex", gap: "1.5rem" }}>
            <Link href="/login">
              <Button asChild size="lg" style={{ background: "#fff", color: "#000", ...homeButtonShadow }} className="home-shadow-btn">
                <span style={{ color: "#000" }}>Get Started</span>
              </Button>
            </Link>
            <Link href="/login">
              <Button
                size="lg"
                style={{ background: "#fff", color: "#000", ...homeButtonShadow }}
                className="home-shadow-btn"
              >
                <span style={{ color: "#000" }}>Log In</span>
              </Button>
            </Link>
          </div>
        </div>
        {/* Placeholder for illustration */}
        <div style={{ minWidth: "320px", minHeight: "240px", background: "rgba(79,209,197,0.08)", borderRadius: "24px", display: "flex", alignItems: "center", justifyContent: "center" }}>
          {/* You can replace this with an SVG or image */}
          <span style={{ color: "#4fd1c5", fontSize: "1.2rem" }}>[ Illustration Here ]</span>
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
