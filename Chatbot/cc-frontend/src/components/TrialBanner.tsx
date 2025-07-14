"use client";
import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { X, Clock, CreditCard, CheckCircle } from "lucide-react";
import { useRouter } from "next/navigation";

interface TrialBannerProps {
  onDismiss?: () => void;
  showDismiss?: boolean;
}

export default function TrialBanner({ onDismiss, showDismiss = true }: TrialBannerProps) {
  const [trialDaysRemaining, setTrialDaysRemaining] = useState(5);
  const [isVisible, setIsVisible] = useState(true);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  useEffect(() => {
    // Calculate trial days remaining
    const trialStartDate = sessionStorage.getItem('trialStartDate');
    if (trialStartDate) {
      const startDate = new Date(trialStartDate);
      const currentDate = new Date();
      const diffTime = 5 * 24 * 60 * 60 * 1000 - (currentDate.getTime() - startDate.getTime()); // 5 days in ms
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      setTrialDaysRemaining(Math.max(0, diffDays));
    }
  }, []);

  const handleStripeCheckout = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/stripe/checkout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          priceId: 'price_1RUql52KmmBYwJTHegFyjNV4', // Monthly subscription price ID
          quantity: 1,
        }),
      });

      const data = await response.json();
      if (data.sessionId) {
        // Use the existing StripeCheckoutButton logic
        const stripe = await import('@stripe/stripe-js').then(m => 
          m.loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!)
        );
        const stripeInstance = await stripe;
        if (stripeInstance) {
          const result = await stripeInstance.redirectToCheckout({
            sessionId: data.sessionId,
          });
          if (result.error) {
            console.error('Stripe checkout error:', result.error);
          }
        }
      }
    } catch (error) {
      console.error('Error creating checkout session:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDismiss = () => {
    setIsVisible(false);
    if (onDismiss) {
      onDismiss();
    }
  };

  if (!isVisible) return null;

  // Show different banners based on trial status
  if (trialDaysRemaining > 0) {
    return (
      <div className="bg-gradient-to-r from-blue-600 to-blue-800 text-white p-4 rounded-lg shadow-lg relative mb-4">
        {showDismiss && (
          <button
            onClick={handleDismiss}
            className="absolute top-2 right-2 text-white hover:text-gray-200 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        )}
        
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-300" />
              <span className="font-semibold">Trial activated — {trialDaysRemaining} days remaining</span>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="text-sm opacity-90 hidden sm:block">
              Secure your spot after trial — $49/month, cancel anytime
            </div>
            <Button
              onClick={handleStripeCheckout}
              disabled={loading}
              variant="secondary"
              size="sm"
              className="bg-white text-blue-800 hover:bg-gray-100 flex items-center gap-2"
            >
              <CreditCard className="h-4 w-4" />
              {loading ? "Setting up..." : "Set Up Payment"}
            </Button>
          </div>
        </div>
        
        {/* Mobile layout */}
        <div className="sm:hidden mt-3 text-sm">
          <div className="mb-2 opacity-90">
            Secure your spot after trial — $49/month, cancel anytime
          </div>
        </div>
      </div>
    );
  }

  // Trial expired banner
  return (
    <div className="bg-gradient-to-r from-red-600 to-red-800 text-white p-4 rounded-lg shadow-lg relative mb-4">
      {showDismiss && (
        <button
          onClick={handleDismiss}
          className="absolute top-2 right-2 text-white hover:text-gray-200 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      )}
      
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-yellow-300" />
            <span className="font-semibold">Trial expired — Upgrade to continue access</span>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="text-sm opacity-90 hidden sm:block">
            Only $49/month — Cancel anytime
          </div>
          <Button
            onClick={handleStripeCheckout}
            disabled={loading}
            variant="secondary"
            size="sm"
            className="bg-white text-red-800 hover:bg-gray-100 flex items-center gap-2"
          >
            <CreditCard className="h-4 w-4" />
            {loading ? "Setting up..." : "Upgrade Now"}
          </Button>
        </div>
      </div>
      
      {/* Mobile layout */}
      <div className="sm:hidden mt-3 text-sm">
        <div className="mb-2 opacity-90">
          Only $49/month — Cancel anytime
        </div>
      </div>
    </div>
  );
} 