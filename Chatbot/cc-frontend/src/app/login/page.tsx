import React from 'react';
import { GalleryVerticalEnd } from "lucide-react"
import { LoginForm } from "@/components/login-form"
export default function LoginPage() {
  return (
    <div
      className="flex min-h-svh flex-col items-center justify-center gap-6 p-6 md:p-10"
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #1e2a78 0%, #3a3d9f 100%)",
      }}
    >
      <div className="flex w-full max-w-sm flex-col gap-6">
        {/* Promotional Banner */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-800 text-white p-4 rounded-lg shadow-lg text-center border-2 border-blue-400">
          <div className="flex items-center justify-center gap-2 text-lg font-bold mb-2">
            🚨 Get Access Now
          </div>
          <div className="text-sm leading-relaxed">
            <div className="mb-1">Start pulling Houston foreclosure leads today.</div>
            <div className="mb-1">🔓 5-day free trial → then just $49/mo</div>
            <div>💸 Cancel anytime — no questions asked.</div>
          </div>
        </div>
        
        <div className="flex items-center gap-2 self-center font-medium" style={{ color: '#FFFFFF' }}>
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <GalleryVerticalEnd className="size-4" />
          </div>
          Teniola Inc.
        </div>
        <LoginForm />
      </div>
    </div>
  )
}
