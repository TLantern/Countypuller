"use client";
import React from "react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { signIn } from "next-auth/react";

const homeButtonShadow = {
  boxShadow: '0 4px 24px 0 rgba(224,224,224,0.6)',
  transition: 'box-shadow 0.2s',
};
const homeButtonHover = {
  boxShadow: '0 8px 32px 0 rgba(224,224,224,0.8)',
};

function useIsMobile() {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(max-width: 768px)').matches;
}

export default function Home() {
  const [isMobile, setIsMobile] = React.useState(false);
  
  React.useEffect(() => {
    const checkIfMobile = () => {
      setIsMobile(window.matchMedia('(max-width: 768px)').matches);
    };
    
    checkIfMobile();
    const mediaQuery = window.matchMedia('(max-width: 768px)');
    mediaQuery.addListener(checkIfMobile);
    
    return () => mediaQuery.removeListener(checkIfMobile);
  }, []);
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
          padding: isMobile ? "1rem 1rem" : "1.5rem 4rem",
          flexDirection: isMobile ? "column" : "row",
          flexWrap: "wrap",
          position: "relative",
          minHeight: isMobile ? "auto" : "80px"
        }}
      >
        <div style={{ 
          fontWeight: 700, 
          fontSize: isMobile ? "1.2rem" : "1.5rem", 
          letterSpacing: "1px", 
          marginBottom: isMobile ? "1rem" : 0,
          textAlign: isMobile ? "center" : "left"
        }}>
          Clerk<span style={{ color: "#4fd1c5" }}> Crawler</span>
        </div>
        
        {/* Centered Navigation Items */}
        {!isMobile && (
          <nav style={{ 
            display: "flex", 
            gap: "2rem", 
            alignItems: "center",
            position: "absolute",
            left: "50%",
            transform: "translateX(-50%)"
          }}>
            <a href="#" style={{ color: "#fff", textDecoration: "none", fontSize: "1rem" }}>Home</a>
            <a href="#" style={{ color: "#fff", textDecoration: "none", fontSize: "1rem" }}>About us</a>
            <a href="/pricing" style={{ color: "#fff", textDecoration: "none", fontSize: "1rem" }}>Pricing</a>
            <a href="#" style={{ color: "#fff", textDecoration: "none", fontSize: "1rem" }}>Features</a>
          </nav>
        )}
        
        {/* Mobile Navigation */}
        {isMobile && (
          <nav style={{ 
            display: "flex", 
            gap: "0.8rem", 
            alignItems: "center", 
            flexWrap: "wrap", 
            flexDirection: "row", 
            justifyContent: "center",
            width: "100%", 
            marginBottom: "1rem"
          }}>
            <a href="#" style={{ color: "#fff", textDecoration: "none", fontSize: "0.9rem", padding: "0.5rem" }}>Home</a>
            <a href="#" style={{ color: "#fff", textDecoration: "none", fontSize: "0.9rem", padding: "0.5rem" }}>About us</a>
            <a href="/pricing" style={{ color: "#fff", textDecoration: "none", fontSize: "0.9rem", padding: "0.5rem" }}>Pricing</a>
            <a href="#" style={{ color: "#fff", textDecoration: "none", fontSize: "0.9rem", padding: "0.5rem" }}>Features</a>
          </nav>
        )}
        
        {/* Log In Button */}
        <Link href="/login">
          <Button
            asChild
            style={{ 
              background: "#fff", 
              color: "#000", 
              width: isMobile ? "200px" : "auto",
              padding: isMobile ? "0.6rem 1.2rem" : "0.5rem 1rem",
              fontSize: isMobile ? "0.9rem" : "1rem"
            }}
          >
            <span style={{ color: "#000" }}>Log In</span>
          </Button>
        </Link>
      </header>

      {/* Hero Section */}
      <main
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: isMobile ? "2rem 1rem" : "4rem 2rem",
          textAlign: "center",
          minHeight: isMobile ? "70vh" : "60vh",
        }}
      >
        <div style={{ maxWidth: isMobile ? "100%" : "800px", width: "100%" }}>
          <h1 style={{ 
            fontSize: isMobile ? "1.6rem" : "3.5rem", 
            fontWeight: 800, 
            marginBottom: isMobile ? "1.5rem" : "2rem",
            lineHeight: isMobile ? 1.3 : 1.2,
            textShadow: "1px 1px 0 rgba(0,0,0,0.3), -1px -1px 0 rgba(0,0,0,0.3), 1px -1px 0 rgba(0,0,0,0.3), -1px 1px 0 rgba(0,0,0,0.3)",
            padding: isMobile ? "0 0.5rem" : "0"
          }}>
            Find <span style={{ color: "#4fd1c5" }}>off-market</span> properties <span style={{ color: "#4fd1c5" }}>10x faster</span> while avoiding stale and recycled leads
          </h1>
          <p style={{ 
            fontSize: isMobile ? "1rem" : "1.4rem", 
            marginBottom: isMobile ? "2rem" : "3rem", 
            color: "#c3c6f1",
            maxWidth: isMobile ? "100%" : "600px",
            margin: isMobile ? "0 auto 2rem auto" : "0 auto 3rem auto",
            padding: isMobile ? "0 0.5rem" : "0",
            lineHeight: isMobile ? 1.5 : 1.4
          }}>
            Save hours of manual work and close more deals with our powerful, automated research platform.
          </p>
                    <div style={{ 
            display: "flex", 
            gap: isMobile ? "0.8rem" : "1.5rem", 
            flexWrap: "wrap", 
            flexDirection: isMobile ? "column" : "row", 
            justifyContent: "center",
            alignItems: "center",
            marginBottom: isMobile ? "1.5rem" : "2rem",
            padding: isMobile ? "0 0.5rem" : "0"
          }}>
            <Link href="/pricing">
              <Button asChild size={isMobile ? "default" : "lg"} className="glow-pulse-btn" style={{ 
                background: "#fff", 
                color: "#000", 
                width: isMobile ? "100%" : "auto", 
                minWidth: isMobile ? "auto" : "250px",
                maxWidth: isMobile ? "300px" : "none",
                padding: isMobile ? "0.8rem 1.5rem" : "0.75rem 2rem",
                fontSize: isMobile ? "0.9rem" : "1rem",
                position: 'relative', 
                zIndex: 1 
              }}>
                <span style={{ color: "#000", position: 'relative', zIndex: 2 }}>Start 5 Day Free Trial</span>
              </Button>
            </Link>
            <Button
              size={isMobile ? "default" : "lg"}
              onClick={() => signIn("google", { callbackUrl: "/dashboard" })}
              style={{ 
                background: "#fff", 
                color: "#000", 
                width: isMobile ? "100%" : "auto",
                minWidth: isMobile ? "auto" : "250px",
                maxWidth: isMobile ? "300px" : "none",
                padding: isMobile ? "0.8rem 1.5rem" : "0.75rem 2rem",
                fontSize: isMobile ? "0.9rem" : "1rem",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: isMobile ? "6px" : "8px",
                border: "1px solid #dadce0",
                borderRadius: "8px",
                boxShadow: "0 1px 3px rgba(0,0,0,0.1)"
              }}
            >
              <svg width={isMobile ? "16" : "18"} height={isMobile ? "16" : "18"} viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              <span style={{ color: "#000", fontWeight: 500 }}>Continue with Google</span>
            </Button>
          </div>
          <div style={{
            background: 'linear-gradient(90deg, #3b82f6 0%, #7c3aed 100%)',
            color: '#fff',
            fontWeight: 700,
            fontSize: isMobile ? '0.9rem' : '1.18rem',
            borderRadius: isMobile ? 12 : 16,
            padding: isMobile ? '0.6rem 0.8rem' : '1rem 2rem',
            boxShadow: '0 4px 24px 0 rgba(59,130,246,0.18)',
            textAlign: 'center',
            letterSpacing: '0.01em',
            lineHeight: isMobile ? 1.3 : 1.4,
            border: '2px solid #3b82f6',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: isMobile ? '0.3rem' : '0.5rem',
            position: 'relative',
            zIndex: 2,
            maxWidth: isMobile ? "95%" : "600px",
            margin: isMobile ? "0 auto" : "0 auto"
          }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', marginRight: 8 }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" style={{ marginRight: 4 }} xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="10" fill="#3b82f6" stroke="#7c3aed" strokeWidth="2"/><path d="M8 12l2.5 2.5L16 9" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </span>
            <em style={{ fontStyle: 'normal', background: 'none', color: '#fff' }}>
              Used by 74 investors in TX to close 38+ deals this year. <span style={{ color: '#ffe066', fontWeight: 800, marginLeft: 4 }}>Now live in Harris, Dallas, and Travis Counties — new counties weekly.</span>
            </em>
          </div>
        </div>
      </main>
      
      {/* Demo Video Section */}
      <section style={{ 
        width: '100%', 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center', 
        padding: isMobile ? "1.5rem 1rem" : "3rem 2rem",
        marginTop: isMobile ? '1rem' : '2rem'
      }}>
        <div style={{ width: isMobile ? '100%' : '60%', maxWidth: isMobile ? '100%' : '800px' }}>
          <h3 style={{
            color: '#fff',
            fontWeight: 800,
            fontSize: isMobile ? '1.4rem' : '2.8rem',
            marginBottom: isMobile ? 12 : 18,
            textAlign: 'center',
            textShadow: '0 0 12px #3b82f6',
            lineHeight: 1.1,
            padding: isMobile ? '0 0.5rem' : '0'
          }}>
            Clerk Crawler Demo
          </h3>
          <div style={{ 
            borderRadius: isMobile ? 16 : 32, 
            boxShadow: isMobile ? '0 0 24px 8px #3b82f6, 0 0 0 4px #fff2' : '0 0 56px 16px #3b82f6, 0 0 0 8px #fff2', 
            background: 'rgba(59,130,246,0.15)', 
            padding: isMobile ? 12 : 20, 
            width: '100%' 
          }}>
            <div style={{ position: 'relative', paddingBottom: '56.25%', height: 0 }}>
              <iframe src="https://www.loom.com/embed/e1a6688e0d654818b61464c71fe98c00?sid=45ff9108-8af0-4762-b6cf-ce30af5d337e" frameBorder="0" allowFullScreen style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', borderRadius: isMobile ? 12 : 24 }}></iframe>
            </div>
          </div>
        </div>
      </section>
      
      {/* Our Mission section */}
      <section style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', margin: isMobile ? '2.5rem 0 0 0' : '3.5rem 0 0 0' }}>
        <h3 style={{
          color: '#fff',
          fontWeight: 800,

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
