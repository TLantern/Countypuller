import StripeCheckoutButton from '@/components/StripeCheckoutButton';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-3xl font-extrabold text-gray-900 sm:text-4xl">
            Choose Your Plan
          </h2>
          <p className="mt-4 text-xl text-gray-600">
            Select the perfect plan for your property research needs
          </p>
        </div>

        <div className="mt-12 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-2">
          {/* 2 Counties/Unlimited LLM use - Yearly */}
          <Card>
            <CardHeader>
              <CardTitle>2 Counties/Unlimited LLM use</CardTitle>
              <CardDescription>Best value for teams and power users. Unlimited AI property research in 2 counties. <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-bold ml-2">3-Day Free Trial</span></CardDescription>
              <div className="mt-4">
                <span className="text-4xl font-bold">$999</span>
                <span className="text-base font-medium text-gray-500">/year</span>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                <li>Unlimited LLM (AI) property lookups</li>
                <li>Access to 2 counties</li>
                <li>Priority support</li>
              </ul>
            </CardContent>
            <CardFooter>
              <StripeCheckoutButton priceId="price_1RUqn72KmmBYwJTHrVxBWEZT"> {/* Replace with your Stripe Price ID */}
                Start Free Trial
              </StripeCheckoutButton>
            </CardFooter>
          </Card>

          {/* 2 Counties/Unlimited LLM use - Monthly */}
          <Card>
            <CardHeader>
              <CardTitle>2 Counties/Unlimited LLM use</CardTitle>
              <CardDescription>Flexible monthly access for unlimited AI research in 2 counties. <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-bold ml-2">3-Day Free Trial</span></CardDescription>
              <div className="mt-4">
                <span className="text-4xl font-bold">$79</span>
                <span className="text-base font-medium text-gray-500">/month</span>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                <li>Unlimited LLM (AI) property lookups</li>
                <li>Access to 2 counties</li>
                <li>Email support</li>
              </ul>
            </CardContent>
            <CardFooter>
              <StripeCheckoutButton priceId="price_1RUqme2KmmBYwJTHoiOjENPb"> {/* Replace with your Stripe Price ID */}
                Start Free Trial
              </StripeCheckoutButton>
            </CardFooter>
          </Card>

          {/* 1 County/Limited LLM use - Yearly */}
          <Card>
            <CardHeader>
              <CardTitle>1 County/Limited LLM use</CardTitle>
              <CardDescription>Annual plan for focused research in a single county with limited AI usage. <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-bold ml-2">3-Day Free Trial</span></CardDescription>
              <div className="mt-4">
                <span className="text-4xl font-bold">$490</span>
                <span className="text-base font-medium text-gray-500">/year</span>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                <li>Limited LLM (AI) property lookups</li>
                <li>Access to 1 county</li>
                <li>Email support</li>
              </ul>
            </CardContent>
            <CardFooter>
              <StripeCheckoutButton priceId="price_1RUqlT2KmmBYwJTHcMz9S41M"> {/* Replace with your Stripe Price ID */}
                Start Free Trial
              </StripeCheckoutButton>
            </CardFooter>
          </Card>

          {/* 1 County/Limited LLM use - Monthly */}
          <Card>
            <CardHeader>
              <CardTitle>1 County/Limited LLM use</CardTitle>
              <CardDescription>Monthly plan for individuals needing limited AI research in one county. <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-bold ml-2">3-Day Free Trial</span></CardDescription>
              <div className="mt-4">
                <span className="text-4xl font-bold">$49</span>
                <span className="text-base font-medium text-gray-500">/month</span>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                <li>Limited LLM (AI) property lookups</li>
                <li>Access to 1 county</li>
                <li>Email support</li>
              </ul>
            </CardContent>
            <CardFooter>
              <StripeCheckoutButton priceId="price_1RUql52KmmBYwJTHegFyjNV4"> {/* Replace with your Stripe Price ID */}
                Start Free Trial
              </StripeCheckoutButton>
            </CardFooter>
          </Card>

          {/* Pro Plan */}
          <Card>
            <CardHeader>
              <CardTitle>Pro Plan</CardTitle>
              <CardDescription>All features included. <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-bold ml-2">3-Day Free Trial</span></CardDescription>
              <div className="mt-4">
                <span className="text-4xl font-bold">$29</span>
                <span className="text-base font-medium text-gray-500">/month</span>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                <li>All features included</li>
                <li>Cancel anytime before trial ends</li>
              </ul>
            </CardContent>
            <CardFooter>
              <StripeCheckoutButton priceId="price_1RUqoT2KmmBYwJTHrVxBWEZT"> {/* Replace with your Stripe Price ID */}
                Start Free Trial
              </StripeCheckoutButton>
            </CardFooter>
          </Card>
        </div>
      </div>
    </div>
  );
} 