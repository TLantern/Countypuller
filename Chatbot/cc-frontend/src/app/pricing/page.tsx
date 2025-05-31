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

        <div className="mt-12 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {/* Basic Plans */}
          <Card className="relative">
            <CardHeader>
              <CardTitle className="text-2xl font-bold">Basic</CardTitle>
              <CardDescription>Perfect for getting started</CardDescription>
              <div className="mt-4">
                <span className="text-4xl font-bold">$49</span>
                <span className="text-base font-medium text-gray-500">/month</span>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Up to 100 searches/month
                </li>
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Basic property data
                </li>
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Email support
                </li>
              </ul>
            </CardContent>
            <CardFooter>
              <StripeCheckoutButton 
                priceId="price_basic_plan_id" // Replace with your actual Stripe Price ID
                className="w-full"
              >
                Start Basic Plan
              </StripeCheckoutButton>
            </CardFooter>
          </Card>

          {/* Pro Plan */}
          <Card className="relative border-blue-500 border-2">
            <div className="absolute top-0 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
              <span className="bg-blue-500 text-white px-4 py-1 text-sm font-medium rounded-full">
                Most Popular
              </span>
            </div>
            <CardHeader>
              <CardTitle className="text-2xl font-bold">Pro</CardTitle>
              <CardDescription>Best for professionals</CardDescription>
              <div className="mt-4">
                <span className="text-4xl font-bold">$99</span>
                <span className="text-base font-medium text-gray-500">/month</span>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Up to 1,000 searches/month
                </li>
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Advanced property data
                </li>
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  API access
                </li>
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Priority support
                </li>
              </ul>
            </CardContent>
            <CardFooter>
              <StripeCheckoutButton 
                priceId="price_pro_plan_id" // Replace with your actual Stripe Price ID
                className="w-full"
              >
                Start Pro Plan
              </StripeCheckoutButton>
            </CardFooter>
          </Card>

          {/* Enterprise Plan */}
          <Card className="relative">
            <CardHeader>
              <CardTitle className="text-2xl font-bold">Enterprise</CardTitle>
              <CardDescription>For large organizations</CardDescription>
              <div className="mt-4">
                <span className="text-4xl font-bold">$299</span>
                <span className="text-base font-medium text-gray-500">/month</span>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Unlimited searches
                </li>
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Premium property data
                </li>
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Full API access
                </li>
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  24/7 dedicated support
                </li>
                <li className="flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Custom integrations
                </li>
              </ul>
            </CardContent>
            <CardFooter>
              <StripeCheckoutButton 
                priceId="price_enterprise_plan_id" // Replace with your actual Stripe Price ID
                className="w-full"
              >
                Start Enterprise Plan
              </StripeCheckoutButton>
            </CardFooter>
          </Card>
        </div>
      </div>
    </div>
  );
} 