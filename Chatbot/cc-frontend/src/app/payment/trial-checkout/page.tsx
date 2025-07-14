"use client";
import React, { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CheckCircle, Clock, CreditCard } from "lucide-react";

export default function TrialCheckoutPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [trialDaysRemaining, setTrialDaysRemaining] = useState(5);

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

  return (
    <div
      className="flex min-h-svh flex-col items-center justify-center gap-6 p-6 md:p-10"
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #1e2a78 0%, #3a3d9f 100%)",
      }}
    >
      <div className="flex w-full max-w-lg flex-col gap-6">
        {/* Trial Activated Banner */}
        <div className="bg-gradient-to-r from-green-600 to-green-800 text-white p-6 rounded-lg shadow-lg text-center border-2 border-green-400">
          <div className="flex items-center justify-center gap-3 text-2xl font-bold mb-3">
            <CheckCircle className="h-8 w-8" />
            Trial Activated!
          </div>
          <div className="text-lg mb-2">
            🎉 Welcome to Clerk Crawler!
          </div>
          <div className="text-sm opacity-90">
            Your 5-day free trial has started. Access all features now!
          </div>
        </div>

        {/* Trial Status Card */}
        <Card>
          <CardHeader className="text-center">
            <CardTitle className="text-2xl flex items-center justify-center gap-2">
              <Clock className="h-6 w-6 text-blue-600" />
              {trialDaysRemaining} Days Remaining
            </CardTitle>
            <CardDescription className="text-lg">
              Start pulling Houston foreclosure leads immediately
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Features List */}
            <div className="bg-gray-50 p-4 rounded-lg">
              <h3 className="font-semibold mb-3 text-gray-800">What you get during your trial:</h3>
              <ul className="space-y-2 text-sm text-gray-700">
                <li className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  Unlimited Houston foreclosure lead pulls
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  Real-time property data and analytics
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  Advanced filtering and search tools
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  Export capabilities (CSV, PDF)
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  Priority customer support
                </li>
              </ul>
            </div>

            {/* Call to Action */}
            <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
              <div className="text-center">
                <div className="text-lg font-semibold text-blue-800 mb-2">
                  🔒 Secure Your Spot After Trial
                </div>
                <div className="text-sm text-blue-700 mb-3">
                  Only $49/month after 5 days • Cancel anytime • No questions asked
                </div>
                <Button 
                  onClick={handleStripeCheckout}
                  disabled={loading}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                  size="lg"
                >
                  <CreditCard className="h-5 w-5 mr-2" />
                  {loading ? "Setting up payment..." : "Set Up Payment Method"}
                </Button>
              </div>
            </div>

            {/* Trust Signals */}
            <div className="text-center text-sm text-gray-600 space-y-1">
              <div>🔐 Secure payment processing by Stripe</div>
              <div>📧 Email reminders before trial ends</div>
              <div>❌ Easy cancellation anytime</div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 