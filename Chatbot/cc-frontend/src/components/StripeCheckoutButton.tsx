"use client";

import { useState } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Button } from '@/components/ui/button';

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!);

interface StripeCheckoutButtonProps {
  priceId: string;
  quantity?: number;
  children: React.ReactNode;
  className?: string;
}

export default function StripeCheckoutButton({ 
  priceId, 
  quantity = 1, 
  children, 
  className 
}: StripeCheckoutButtonProps) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);

    try {
      if (!priceId) {
        alert('No priceId provided!');
        setLoading(false);
        return;
      }

      console.log('About to call /api/stripe/checkout', { priceId, quantity });
      const stripe = await stripePromise;

      if (!stripe) {
        alert('Stripe failed to load');
        setLoading(false);
        return;
      }

      // Call your API to create a checkout session
      const response = await fetch('/api/stripe/checkout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          priceId,
          quantity,
        }),
      });

      const data = await response.json();

      if (data.error) {
        alert('Server error: ' + data.error);
        setLoading(false);
        return;
      }

      if (!data.sessionId) {
        alert('No sessionId returned from server.');
        setLoading(false);
        return;
      }

      // Redirect to Stripe Checkout
      const result = await stripe.redirectToCheckout({
        sessionId: data.sessionId,
      });

      if (result.error) {
        alert('Stripe checkout error: ' + result.error.message);
        console.error('Stripe checkout error:', result.error);
      }
    } catch (error) {
      alert('Error: ' + (error as any).message);
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button 
      onClick={handleClick} 
      disabled={loading}
      className={className}
    >
      {loading ? 'Loading...' : children}
    </Button>
  );
} 