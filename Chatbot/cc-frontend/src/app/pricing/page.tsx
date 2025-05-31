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
              <CardDescription>Best value for teams and power users. Unlimited AI property research in 2 counties.</CardDescription>
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
              <StripeCheckoutButton priceId="prod_SPg9VrSjD6iZ0k"> {/* Replace with your Stripe Price ID */}
                Choose Yearly
              </StripeCheckoutButton>
            </CardFooter>
          </Card>

          {/* 2 Counties/Unlimited LLM use - Monthly */}
          <Card>
            <CardHeader>
              <CardTitle>2 Counties/Unlimited LLM use</CardTitle>
              <CardDescription>Flexible monthly access for unlimited AI research in 2 counties.</CardDescription>
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
              <StripeCheckoutButton priceId="prod_SPg80MRwVfwVgs"> {/* Replace with your Stripe Price ID */}
                Choose Monthly
              </StripeCheckoutButton>
            </CardFooter>
          </Card>

          {/* 1 County/Limited LLM use - Yearly */}
          <Card>
            <CardHeader>
              <CardTitle>1 County/Limited LLM use</CardTitle>
              <CardDescription>Annual plan for focused research in a single county with limited AI usage.</CardDescription>
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
              <StripeCheckoutButton priceId="prod_SPg7UuvsFDJlE1"> {/* Replace with your Stripe Price ID */}
                Choose Yearly
              </StripeCheckoutButton>
            </CardFooter>
          </Card>

          {/* 1 County/Limited LLM use - Monthly */}
          <Card>
            <CardHeader>
              <CardTitle>1 County/Limited LLM use</CardTitle>
              <CardDescription>Monthly plan for individuals needing limited AI research in one county.</CardDescription>
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
              <StripeCheckoutButton priceId="prod_SPg74XECK4lzYt"> {/* Replace with your Stripe Price ID */}
                Choose Monthly
              </StripeCheckoutButton>
            </CardFooter>
          </Card>
        </div>
      </div>
    </div>
  );
} 