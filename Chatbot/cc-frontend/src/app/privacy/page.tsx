import React from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';

export default function PrivacyPolicy() {
  const isMobile = typeof window !== 'undefined' && window.matchMedia('(max-width: 600px)').matches;

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #1e2a78 0%, #3a3d9f 100%)",
        color: "#fff",
        padding: "0",
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
        <Link href="/" style={{ textDecoration: "none" }}>
          <div style={{ fontWeight: 700, fontSize: isMobile ? "1.1rem" : "1.5rem", letterSpacing: "1px", marginBottom: isMobile ? 12 : 0, color: "#fff" }}>
            Clerk<span style={{ color: "#4fd1c5" }}> Crawler</span>
          </div>
        </Link>
        <nav style={{ display: "flex", gap: isMobile ? "1rem" : "2rem", alignItems: "center", flexWrap: "wrap", flexDirection: isMobile ? "column" : "row", width: isMobile ? "100%" : undefined, marginTop: isMobile ? 12 : 0 }}>
          <Link href="/" style={{ color: "#fff", textDecoration: "none" }}>Home</Link>
          <a href="#" style={{ color: "#fff", textDecoration: "none" }}>About us</a>
          <Link href="/pricing" style={{ color: "#fff", textDecoration: "none" }}>Pricing</Link>
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

      {/* Privacy Policy Content */}
      <main style={{ 
        maxWidth: "800px", 
        margin: "0 auto", 
        padding: isMobile ? "2rem 1rem" : "2rem 4rem",
        backgroundColor: "rgba(255, 255, 255, 0.1)",
        borderRadius: "12px",
        marginTop: "2rem",
        marginBottom: "2rem",
        backdropFilter: "blur(10px)",
        border: "1px solid rgba(255, 255, 255, 0.2)"
      }}>
        <h1 style={{ 
          fontSize: isMobile ? "1.8rem" : "2.5rem", 
          fontWeight: "800", 
          marginBottom: "1.5rem",
          textAlign: "center",
          color: "#4fd1c5"
        }}>
          Privacy Policy
        </h1>
        
        <div style={{ fontSize: isMobile ? "0.9rem" : "1rem", lineHeight: "1.6", color: "#e2e8f0" }}>
          <p style={{ marginBottom: "1.5rem", textAlign: "center", fontWeight: "600" }}>
            Effective Date: July 15, 2025
          </p>

          <p style={{ marginBottom: "2rem" }}>
            At ClerkCrawler, we are committed to protecting your privacy. This Privacy Policy outlines how we collect, use, and protect your personal information when you use our services.
          </p>

          <h2 style={{ 
            fontSize: isMobile ? "1.3rem" : "1.5rem", 
            fontWeight: "700", 
            marginBottom: "1rem", 
            marginTop: "2rem",
            color: "#4fd1c5"
          }}>
            Information We Collect
          </h2>
          <ul style={{ marginBottom: "2rem", paddingLeft: "1.5rem" }}>
            <li style={{ marginBottom: "0.5rem" }}>Your name, email address, and contact info when you sign up or submit a form.</li>
            <li style={{ marginBottom: "0.5rem" }}>Your activity on our website and dashboard.</li>
            <li style={{ marginBottom: "0.5rem" }}>Deal preferences and zip codes (if submitted through forms or surveys).</li>
          </ul>

          <h2 style={{ 
            fontSize: isMobile ? "1.3rem" : "1.5rem", 
            fontWeight: "700", 
            marginBottom: "1rem", 
            marginTop: "2rem",
            color: "#4fd1c5"
          }}>
            How We Use Your Information
          </h2>
          <ul style={{ marginBottom: "2rem", paddingLeft: "1.5rem" }}>
            <li style={{ marginBottom: "0.5rem" }}>To deliver foreclosure leads and personalized property updates.</li>
            <li style={{ marginBottom: "0.5rem" }}>To improve our service, website, and communication experience.</li>
            <li style={{ marginBottom: "0.5rem" }}>To contact you with updates, new features, or offers (you can opt out at any time).</li>
          </ul>

          <h2 style={{ 
            fontSize: isMobile ? "1.3rem" : "1.5rem", 
            fontWeight: "700", 
            marginBottom: "1rem", 
            marginTop: "2rem",
            color: "#4fd1c5"
          }}>
            Data Sharing
          </h2>
          <ul style={{ marginBottom: "2rem", paddingLeft: "1.5rem" }}>
            <li style={{ marginBottom: "0.5rem" }}>We do not sell or rent your personal information.</li>
            <li style={{ marginBottom: "0.5rem" }}>We may share data with trusted vendors who help us operate ClerkCrawler (e.g. email services, CRM tools), under strict confidentiality.</li>
          </ul>

          <h2 style={{ 
            fontSize: isMobile ? "1.3rem" : "1.5rem", 
            fontWeight: "700", 
            marginBottom: "1rem", 
            marginTop: "2rem",
            color: "#4fd1c5"
          }}>
            Cookies & Tracking
          </h2>
          <p style={{ marginBottom: "2rem" }}>
            We use cookies and similar tracking technologies to personalize your experience and analyze web traffic.
          </p>

          <h2 style={{ 
            fontSize: isMobile ? "1.3rem" : "1.5rem", 
            fontWeight: "700", 
            marginBottom: "1rem", 
            marginTop: "2rem",
            color: "#4fd1c5"
          }}>
            Your Rights
          </h2>
          <p style={{ marginBottom: "1rem" }}>
            You can request access, correction, or deletion of your data at any time by contacting us at:
          </p>
          <p style={{ marginBottom: "2rem", fontWeight: "600", color: "#4fd1c5" }}>
            📧 safeharbouragent@gmail.com
          </p>

          <h2 style={{ 
            fontSize: isMobile ? "1.3rem" : "1.5rem", 
            fontWeight: "700", 
            marginBottom: "1rem", 
            marginTop: "2rem",
            color: "#4fd1c5"
          }}>
            Policy Updates
          </h2>
          <p style={{ marginBottom: "2rem" }}>
            We may update this Privacy Policy. If changes are significant, we'll notify you via email or site notice.
          </p>

          <h2 style={{ 
            fontSize: isMobile ? "1.3rem" : "1.5rem", 
            fontWeight: "700", 
            marginBottom: "1rem", 
            marginTop: "2rem",
            color: "#4fd1c5"
          }}>
            Contact Us
          </h2>
          <div style={{ 
            backgroundColor: "rgba(255, 255, 255, 0.1)", 
            padding: "1.5rem", 
            borderRadius: "8px",
            border: "1px solid rgba(255, 255, 255, 0.2)"
          }}>
            <p style={{ margin: "0", fontWeight: "600" }}>ClerkCrawler Inc.</p>
            <p style={{ margin: "0.5rem 0 0 0" }}>308 Rowmont Blvd</p>
            <p style={{ margin: "0.5rem 0 0 0", color: "#4fd1c5" }}>safeharbouragent@gmail.com</p>
          </div>
        </div>
      </main>
    </div>
  );
} 