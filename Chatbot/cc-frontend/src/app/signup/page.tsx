"use client";
import React, { useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";

function ProviderIcon({ provider }: { provider: string }) {
  switch (provider) {
    case "github":
      return (
        <svg className="h-5 w-5 mr-2" fill="currentColor" viewBox="0 0 24 24"><path d="M12 .5C5.73.5.5 5.73.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56 0-.28-.01-1.02-.02-2-3.2.7-3.88-1.54-3.88-1.54-.53-1.34-1.3-1.7-1.3-1.7-1.06-.72.08-.71.08-.71 1.17.08 1.78 1.2 1.78 1.2 1.04 1.78 2.73 1.27 3.4.97.11-.75.41-1.27.74-1.56-2.55-.29-5.23-1.28-5.23-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.1 11.1 0 0 1 2.9-.39c.98 0 1.97.13 2.9.39 2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.43-2.69 5.41-5.25 5.7.42.36.79 1.09.79 2.2 0 1.59-.01 2.87-.01 3.26 0 .31.21.68.8.56C20.71 21.39 24 17.08 24 12c0-6.27-5.23-11.5-12-11.5z"/></svg>
      );
    case "google":
      return (
        <svg className="h-5 w-5 mr-2" viewBox="0 0 24 24"><g><path fill="#4285F4" d="M21.805 10.023h-9.765v3.955h5.627c-.243 1.3-1.47 3.82-5.627 3.82-3.386 0-6.145-2.8-6.145-6.25s2.759-6.25 6.145-6.25c1.93 0 3.23.82 3.97 1.53l2.71-2.63C17.09 2.61 14.73 1.5 12.04 1.5c-3.7 0-6.8 2.13-8.89 5.22z"/><path fill="#34A853" d="M3.153 7.345l3.29 2.41C7.36 8.13 9.5 6.5 12.04 6.5c1.93 0 3.23.82 3.97 1.53l2.71-2.63C17.09 2.61 14.73 1.5 12.04 1.5c-5.56 0-10.04 4.48-10.04 10s4.48 10 10.04 10c5.8 0 9.6-4.07 9.6-9.8 0-.66-.07-1.16-.17-1.68z"/><path fill="#FBBC05" d="M12.04 21.5c2.69 0 5.05-.89 6.77-2.42l-3.12-2.56c-.87.6-2.01.96-3.65.96-2.8 0-5.17-1.89-6.02-4.44l-3.23 2.5C5.24 19.37 8.37 21.5 12.04 21.5z"/><path fill="#EA4335" d="M21.805 10.023h-9.765v3.955h5.627c-.243 1.3-1.47 3.82-5.627 3.82-3.386 0-6.145-2.8-6.145-6.25s2.759-6.25 6.145-6.25c1.93 0 3.23.82 3.97 1.53l2.71-2.63C17.09 2.61 14.73 1.5 12.04 1.5c-5.56 0-10.04 4.48-10.04 10s4.48 10 10.04 10c5.8 0 9.6-4.07 9.6-9.8 0-.66-.07-1.16-.17-1.68z"/></g></svg>
      );
    case "azure-ad":
      return (
        <svg className="h-5 w-5 mr-2" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10" fill="#0078D4"/><path d="M12 6v6l4 2" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
      );
    default:
      return null;
  }
}

function CredentialSignup() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  function getPasswordStrength(pw: string) {
    if (!pw || pw.length < 6) return 'Weak';
    // Strong: 8+ chars, upper, lower, number
    const strong = pw.length >= 8 && /[A-Z]/.test(pw) && /[a-z]/.test(pw) && /[0-9]/.test(pw);
    // Excellent: 10+ chars, upper, lower, number, symbol
    const excellent = pw.length >= 10 && /[A-Z]/.test(pw) && /[a-z]/.test(pw) && /[0-9]/.test(pw) && /[^A-Za-z0-9]/.test(pw);
    if (excellent) return 'Excellent';
    if (strong) return 'Strong';
    return 'Weak';
  }
  const passwordStrength = getPasswordStrength(password);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      // First, register the user
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, firstName }),
      });
      const data = await res.json();
      if (res.ok) {
        // Registration successful, now sign in
        const result = await signIn("credentials", {
          email,
          password,
          redirect: false, // Don't redirect automatically
        });
        if (result?.error) {
          setError("Failed to sign in after registration");
        } else {
          // Clear onboarding flags so onboarding always shows for new users
          if (typeof window !== 'undefined') {
            sessionStorage.removeItem('onboarded');
            sessionStorage.removeItem('selectedCounty');
            sessionStorage.removeItem('selectedDocTypes');
            // Set trial start date
            sessionStorage.setItem('trialStartDate', new Date().toISOString());
          }
          // Redirect to Stripe checkout instead of dashboard
          router.push("/payment/trial-checkout");
        }
      } else {
        setError(data.error || "Registration failed");
      }
    } catch (error) {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 mt-2">
      <input
        type="text"
        placeholder="Full Name"
        value={firstName}
        onChange={e => setFirstName(e.target.value)}
        className="border border-gray-400 rounded px-3 py-2 bg-white text-black placeholder-black"
        required
        autoComplete="name"
      />
      <input
        type="email"
        placeholder="Email"
        value={email}
        onChange={e => setEmail(e.target.value)}
        className="border border-gray-400 rounded px-3 py-2 bg-white text-black placeholder-black"
        required
        autoComplete="username"
      />
      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={e => setPassword(e.target.value)}
        className="border border-gray-400 rounded px-3 py-2 bg-white text-black placeholder-black"
        required
        autoComplete="new-password"
      />
      <input
        type="password"
        placeholder="Confirm Password"
        value={confirmPassword}
        onChange={e => setConfirmPassword(e.target.value)}
        className="border border-gray-400 rounded px-3 py-2 bg-white text-black placeholder-black"
        required
        autoComplete="new-password"
      />
      {/* Password strength bar and label */}
      <div style={{ height: 8, width: '100%', background: '#eee', borderRadius: 4, marginBottom: 8 }}>
        <div style={{
          height: '100%',
          borderRadius: 4,
          width: passwordStrength === 'Weak' ? '33%' : passwordStrength === 'Strong' ? '66%' : passwordStrength === 'Excellent' ? '100%' : '0%',
          background: passwordStrength === 'Weak' ? '#e53e3e' : passwordStrength === 'Strong' ? '#d69e2e' : passwordStrength === 'Excellent' ? '#38a169' : 'transparent',
          transition: 'width 0.3s, background 0.3s'
        }} />
      </div>
      <div style={{ fontSize: 13, marginBottom: 4, color: passwordStrength === 'Weak' ? '#e53e3e' : passwordStrength === 'Strong' ? '#d69e2e' : '#38a169', fontWeight: 600 }}>
        Password strength: {passwordStrength}
      </div>
      <Button type="submit" className="w-full" disabled={loading || password !== confirmPassword}>
        {loading ? "Signing up..." : "Sign up with Credentials"}
      </Button>
      {error && <div className="text-red-500 text-xs mt-1">{error}</div>}
    </form>
  );
}

export default function SignupPage() {
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
            {/* You can use the same icon as login */}
            <svg className="size-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 .5C5.73.5.5 5.73.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56 0-.28-.01-1.02-.02-2-3.2.7-3.88-1.54-3.88-1.54-.53-1.34-1.3-1.7-1.3-1.7-1.06-.72.08-.71.08-.71 1.17.08 1.78 1.2 1.78 1.2 1.04 1.78 2.73 1.27 3.4.97.11-.75.41-1.27.74-1.56-2.55-.29-5.23-1.28-5.23-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.1 11.1 0 0 1 2.9-.39c.98 0 1.97.13 2.9.39 2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.43-2.69 5.41-5.25 5.7.42.36.79 1.09.79 2.2 0 1.59-.01 2.87-.01 3.26 0 .31.21.68.8.56C20.71 21.39 24 17.08 24 12c0-6.27-5.23-11.5-12-11.5z"/></svg>
          </div>
          Teniola Inc.
        </div>
        <Card>
          <CardHeader className="text-center">
            <CardTitle className="text-xl">Create your account</CardTitle>
            <CardDescription>
              Sign up with your account
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-3">
              <Button
                variant="outline"
                className="w-full flex items-center justify-center"
                onClick={() => signIn("github", { callbackUrl: "/payment/trial-checkout" })}
              >
                <ProviderIcon provider="github" />
                Sign up with GitHub
              </Button>
              <Button
                variant="outline"
                className="w-full flex items-center justify-center"
                onClick={() => signIn("google", { callbackUrl: "/payment/trial-checkout" })}
              >
                <ProviderIcon provider="google" />
                Sign up with Google
              </Button>
              <Button
                variant="outline"
                className="w-full flex items-center justify-center"
                onClick={() => signIn("azure-ad", { callbackUrl: "/payment/trial-checkout" })}
              >
                <ProviderIcon provider="azure-ad" />
                Sign up with Microsoft
              </Button>
              <CredentialSignup />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 