import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { XCircle } from 'lucide-react';

export default function PaymentCancel() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full bg-white shadow-lg rounded-lg p-6 text-center">
        <XCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Payment Cancelled
        </h1>
        <p className="text-gray-600 mb-6">
          Your payment was cancelled. You can try again or return to the dashboard.
        </p>
        <div className="space-y-3">
          <Link href="/dashboard">
            <Button className="w-full">
              Return to Dashboard
            </Button>
          </Link>
          <Link href="/pricing">
            <Button variant="outline" className="w-full">
              Try Again
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
} 