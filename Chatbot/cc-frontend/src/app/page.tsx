import { Button } from "@/components/ui/button";
import Link from "next/link";

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
          County<span style={{ color: "#4fd1c5" }}>Cloud</span>
        </div>
        <nav style={{ display: "flex", gap: "2rem", alignItems: "center" }}>
          <a href="#" style={{ color: "#fff", textDecoration: "none" }}>Home</a>
          <a href="#" style={{ color: "#fff", textDecoration: "none" }}>About us</a>
          <a href="#" style={{ color: "#fff", textDecoration: "none" }}>Pricing</a>
          <a href="#" style={{ color: "#fff", textDecoration: "none" }}>Features</a>
          <Link href="/login" passHref legacyBehavior>
            <Button
              asChild
              variant="outline"
              style={{ marginLeft: "1.5rem", transition: "transform 0.15s" }}
              className="hover:scale-105 hover:border-[#4fd1c5]"
            >
              <a style={{ color: "#000" }}>Log In</a>
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
            <Link href="/login" passHref legacyBehavior>
              <Button asChild size="lg">
                <a>Get Started</a>
              </Button>
            </Link>
            <Link href="/login" passHref legacyBehavior>
            <Button
              variant="outline"
              size="lg"
              style={{ transition: "transform 0.15s" }}
              className="hover:scale-105 hover:border-[#4fd1c5]"
            >
              <a style={{ color: "#000" }}>Log In</a>
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
    </div>
  );
}
