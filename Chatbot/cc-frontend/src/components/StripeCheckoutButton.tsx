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
      console.log('About to call /api/stripe/checkout', { priceId, quantity });
      const stripe = await stripePromise;
      
      if (!stripe) {
        throw new Error('Stripe failed to load');
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

      const { sessionId } = await response.json();

      // Redirect to Stripe Checkout
      const result = await stripe.redirectToCheckout({
        sessionId,
      });

      if (result.error) {
        console.error('Stripe checkout error:', result.error);
      }
    } catch (error) {
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