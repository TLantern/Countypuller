"use client";
import React from "react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import StripeCheckoutButton from '@/components/StripeCheckoutButton';

function useIsMobile() {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(max-width: 600px)').matches;
}

export default function PricingPage() {
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
      <div style={{ 
        textAlign: "center", 
        padding: isMobile ? "2rem 1rem" : "3rem 2rem",
        maxWidth: "1200px",
        margin: "0 auto"
      }}>
        <h1 style={{ 
          fontSize: isMobile ? "2rem" : "3rem", 
          fontWeight: 700, 
          marginBottom: "1rem",
          color: "#fff"
        }}>
          Choose your plan
        </h1>
        <p style={{ 
          fontSize: isMobile ? "1rem" : "1.25rem", 
          color: "#c3c6f1",
          marginBottom: "3rem",
          maxWidth: "600px",
          margin: "0 auto 3rem auto"
        }}>
          Choose Beta for early access flexibility, or go Plus and save thousands in discounts and perks
        </p>

        {/* Pricing Cards */}
        <div style={{
          display: "flex",
          gap: "2rem",
          justifyContent: "center",
          flexDirection: isMobile ? "column" : "row",
          alignItems: "stretch",
          maxWidth: "900px",
          margin: "0 auto"
        }}>
          {/* Beta Plan */}
          <div style={{
            background: "#fff",
            color: "#000",
            borderRadius: "12px",
            padding: "2rem",
            flex: 1,
            minWidth: isMobile ? "100%" : "400px",
            border: "1px solid #e5e7eb",
            position: "relative"
          }}>
            <div style={{ marginBottom: "2rem" }}>
              <h2 style={{ 
                fontSize: "2rem", 
                fontWeight: 700, 
                marginBottom: "0.5rem",
                color: "#1f2937"
              }}>
                Beta
              </h2>
              <p style={{ 
                color: "#6b7280", 
                marginBottom: "0.5rem",
                fontSize: "1rem"
              }}>
                Early access flexibility
              </p>
              <p style={{ 
                color: "#059669", 
                fontWeight: 600,
                fontSize: "0.875rem",
                marginBottom: "1rem"
              }}>
                For the first 10 beta users
              </p>
              <div style={{ marginBottom: "1.5rem" }}>
                <span style={{ 
                  fontSize: "3rem", 
                  fontWeight: 700,
                  color: "#1f2937"
                }}>
                  $49
                </span>
                <span style={{ 
                  color: "#6b7280",
                  fontSize: "1rem"
                }}>
                  / month
                </span>
                <span style={{ 
                  fontSize: "2.5rem", 
                  fontWeight: 700,
                  color: "#1f2937",
                  marginLeft: "1rem"
                }}>
                  $499
                </span>
                <span style={{ 
                  color: "#6b7280",
                  fontSize: "1rem"
                }}>
                  / year
                </span>
              </div>
              <StripeCheckoutButton priceId="price_1RUql52KmmBYwJTHegFyjNV4" className="glow-on-hover">
                Get started
              </StripeCheckoutButton>
            </div>

            <div style={{ marginBottom: "2rem" }}>
              <h3 style={{ 
                fontSize: "1.125rem", 
                fontWeight: 600,
                marginBottom: "1rem",
                color: "#1f2937"
              }}>
                What's Included?
              </h3>
              <ul style={{ 
                listStyle: "none", 
                padding: 0,
                margin: 0
              }}>
                <li style={{ 
                  display: "flex", 
                  alignItems: "center", 
                  marginBottom: "0.75rem",
                  color: "#374151"
                }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" style={{ marginRight: "0.75rem", flexShrink: 0 }}>
                    <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" fill="#10b981"/>
                  </svg>
                  Limited AI property lookup
                </li>
                <li style={{ 
                  display: "flex", 
                  alignItems: "center", 
                  marginBottom: "0.75rem",
                  color: "#374151"
                }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" style={{ marginRight: "0.75rem", flexShrink: 0 }}>
                    <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" fill="#10b981"/>
                  </svg>
                  Access to 1 county
                </li>
                <li style={{ 
                  display: "flex", 
                  alignItems: "center", 
                  marginBottom: "0.75rem",
                  color: "#374151"
                }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" style={{ marginRight: "0.75rem", flexShrink: 0 }}>
                    <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" fill="#10b981"/>
                  </svg>
                  Pull over 20+ records per day
                </li>
              </ul>
            </div>

            <div>
              <h3 style={{ 
                fontSize: "1.125rem", 
                fontWeight: 600,
                marginBottom: "1rem",
                color: "#1f2937"
              }}>
                Expert support
              </h3>
              <ul style={{ 
                listStyle: "none", 
                padding: 0,
                margin: 0
              }}>
                <li style={{ 
                  display: "flex", 
                  alignItems: "center", 
                  marginBottom: "0.75rem",
                  color: "#374151"
                }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" style={{ marginRight: "0.75rem", flexShrink: 0 }}>
                    <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" fill="#10b981"/>
                  </svg>
                  Email support
                </li>
              </ul>
            </div>
          </div>

          {/* Plus Plan */}
          <div style={{
            background: "#fff",
            color: "#000",
            borderRadius: "12px",
            padding: "2rem",
            flex: 1,
            minWidth: isMobile ? "100%" : "400px",
            border: "3px solid #6366f1",
            position: "relative"
          }}>
            {/* Recommended Badge */}
            <div style={{
              position: "absolute",
              top: "-12px",
              right: "20px",
              background: "#6366f1",
              color: "#fff",
              padding: "0.5rem 1rem",
              borderRadius: "20px",
              fontSize: "0.875rem",
              fontWeight: 600,
              transform: "rotate(12deg)"
            }}>
              Recommended
            </div>

            <div style={{ marginBottom: "2rem" }}>
              <h2 style={{ 
                fontSize: "2rem", 
                fontWeight: 700, 
                marginBottom: "0.5rem",
                color: "#1f2937"
              }}>
                Plus
              </h2>
              <p style={{ 
                color: "#6b7280", 
                marginBottom: "1rem",
                fontSize: "1rem"
              }}>
                Save thousands in discounts and perks
              </p>
              <p style={{ 
                color: "#059669", 
                fontWeight: 600,
                fontSize: "0.875rem",
                marginBottom: "1rem"
              }}>
                Annual membership
              </p>
              <div style={{ marginBottom: "1.5rem" }}>
                <span style={{ 
                  fontSize: "3rem", 
                  fontWeight: 700,
                  color: "#1f2937"
                }}>
                  $999
                </span>
                <span style={{ 
                  color: "#6b7280",
                  fontSize: "1rem"
                }}>
                  / year
                </span>
              </div>
              <StripeCheckoutButton priceId="price_1RUqn72KmmBYwJTHrVxBWEZT" className="glow-on-hover">
                Get started
              </StripeCheckoutButton>
            </div>

            <div style={{ marginBottom: "2rem" }}>
              <h3 style={{ 
                fontSize: "1.125rem", 
                fontWeight: 600,
                marginBottom: "1rem",
                color: "#1f2937"
              }}>
                What's Included?
              </h3>
              <ul style={{ 
                listStyle: "none", 
                padding: 0,
                margin: 0
              }}>
                <li style={{ 
                  display: "flex", 
                  alignItems: "center", 
                  marginBottom: "0.75rem",
                  color: "#374151"
                }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" style={{ marginRight: "0.75rem", flexShrink: 0 }}>
                    <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" fill="#10b981"/>
                  </svg>
                  Everything in Beta
                </li>
              </ul>
            </div>

            <div style={{ marginBottom: "2rem" }}>
              <h3 style={{ 
                fontSize: "1.125rem", 
                fontWeight: 600,
                marginBottom: "1rem",
                color: "#1f2937"
              }}>
                Premium Features
              </h3>
              <ul style={{ 
                listStyle: "none", 
                padding: 0,
                margin: 0
              }}>
                <li style={{ 
                  display: "flex", 
                  alignItems: "center", 
                  marginBottom: "0.75rem",
                  color: "#374151"
                }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" style={{ marginRight: "0.75rem", flexShrink: 0 }}>
                    <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" fill="#10b981"/>
                  </svg>
                  Unlimited AI property lookup
                </li>
                <li style={{ 
                  display: "flex", 
                  alignItems: "center", 
                  marginBottom: "0.75rem",
                  color: "#374151"
                }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" style={{ marginRight: "0.75rem", flexShrink: 0 }}>
                    <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" fill="#10b981"/>
                  </svg>
                  Access to 3 counties
                </li>
                <li style={{ 
                  display: "flex", 
                  alignItems: "center", 
                  marginBottom: "0.75rem",
                  color: "#374151"
                }}>
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" style={{ marginRight: "0.75rem", flexShrink: 0 }}>
                    <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" fill="#10b981"/>
                  </svg>
                  Pull over 100+ records in a day
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Compare Plans Section */}
        <div style={{
          marginTop: "4rem",
          padding: "2rem",
          background: "rgba(255, 255, 255, 0.1)",
          borderRadius: "12px",
          maxWidth: "900px",
          margin: "4rem auto 0 auto"
        }}>
          <h2 style={{ 
            fontSize: "2rem", 
            fontWeight: 700, 
            marginBottom: "1rem",
            color: "#fff",
            textAlign: "center"
          }}>
            Compare plans
          </h2>
          <p style={{ 
            color: "#c3c6f1",
            textAlign: "center",
            fontSize: "1rem",
            marginBottom: "2rem"
          }}>
            Expand to see Beta vs Plus
          </p>
          
          <div style={{
            display: "grid",
            gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr",
            gap: "2rem",
            textAlign: "left"
          }}>
            <div>
              <h3 style={{ color: "#fff", fontWeight: 600, marginBottom: "1rem" }}>Beta Plan</h3>
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                <li style={{ color: "#c3c6f1", marginBottom: "0.5rem" }}>• Limited AI property lookup</li>
                <li style={{ color: "#c3c6f1", marginBottom: "0.5rem" }}>• Access to 1 county</li>
                <li style={{ color: "#c3c6f1", marginBottom: "0.5rem" }}>• Pull over 20+ records per day</li>
                <li style={{ color: "#c3c6f1", marginBottom: "0.5rem" }}>• Email support</li>
              </ul>
            </div>
            <div>
              <h3 style={{ color: "#fff", fontWeight: 600, marginBottom: "1rem" }}>Plus Plan</h3>
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                <li style={{ color: "#c3c6f1", marginBottom: "0.5rem" }}>• Everything in Beta</li>
                <li style={{ color: "#c3c6f1", marginBottom: "0.5rem" }}>• Unlimited AI property lookup</li>
                <li style={{ color: "#c3c6f1", marginBottom: "0.5rem" }}>• Access to 3 counties</li>
                <li style={{ color: "#c3c6f1", marginBottom: "0.5rem" }}>• Pull over 100+ records in a day</li>
                <li style={{ color: "#c3c6f1", marginBottom: "0.5rem" }}>• Priority support</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}