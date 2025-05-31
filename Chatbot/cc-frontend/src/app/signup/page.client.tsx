import React, { useState } from 'react';
import { signIn } from 'next-auth/react';

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [firstName, setFirstName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setSuccess(false);
    setLoading(true);
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, firstName, password })
    });
    setLoading(false);
    if (res.ok) {
      setSuccess(true);
      setEmail('');
      setFirstName('');
      setPassword('');
    } else {
      const data = await res.json();
      setError(data.error || 'Registration failed');
    }
  }

  return (
    <div
      className="flex min-h-svh flex-col items-center justify-center gap-6 p-6 md:p-10"
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #1e2a78 0%, #3a3d9f 100%)",
      }}
    >
      <div className="flex w-full max-w-sm flex-col gap-6">
        <a href="#" className="flex items-center gap-2 self-center font-medium" style={{ color: '#fff' }}>
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-primary-foreground">
            {/* Logo or icon here */}
          </div>
          Teniola Inc.
        </a>
        {/* OAuth Providers */}
        <div className="bg-white rounded-lg shadow-md p-6 flex flex-col gap-3">
          <button
            type="button"
            className="bg-black text-white rounded px-4 py-2 font-semibold flex items-center justify-center gap-2 hover:bg-gray-900"
            onClick={() => signIn('github', { callbackUrl: '/dashboard' })}
          >
            <span>Sign up with GitHub</span>
          </button>
          <button
            type="button"
            className="bg-white text-black border border-gray-300 rounded px-4 py-2 font-semibold flex items-center justify-center gap-2 hover:bg-gray-100"
            onClick={() => signIn('google', { callbackUrl: '/dashboard' })}
          >
            <span>Sign up with Google</span>
          </button>
          <button
            type="button"
            className="bg-blue-700 text-white rounded px-4 py-2 font-semibold flex items-center justify-center gap-2 hover:bg-blue-800"
            onClick={() => signIn('azure-ad', { callbackUrl: '/dashboard' })}
          >
            <span>Sign up with Microsoft</span>
          </button>
        </div>
        {/* Divider */}
        <div className="flex items-center gap-2 my-2">
          <hr className="flex-grow border-gray-300" />
          <span className="text-gray-500 text-sm">or</span>
          <hr className="flex-grow border-gray-300" />
        </div>
        {/* Credentials Sign Up Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-md p-6 flex flex-col gap-4">
          <h2 className="text-xl font-semibold text-center">Sign Up</h2>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            className="border rounded px-3 py-2"
          />
          <input
            type="text"
            placeholder="First Name"
            value={firstName}
            onChange={e => setFirstName(e.target.value)}
            required
            className="border rounded px-3 py-2"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            className="border rounded px-3 py-2"
          />
          <button
            type="submit"
            className="bg-blue-700 text-white rounded px-4 py-2 font-semibold hover:bg-blue-800"
            disabled={loading}
          >
            {loading ? 'Signing up...' : 'Sign up'}
          </button>
          {error && <div className="text-red-600 text-sm text-center">{error}</div>}
          {success && <div className="text-green-600 text-sm text-center">Registration successful! You can now log in.</div>}
          <div className="text-center text-sm mt-2">
            Already have an account?{' '}
            <a href="/login" className="underline underline-offset-4">Log in</a>
          </div>
        </form>
      </div>
    </div>
  );
} 