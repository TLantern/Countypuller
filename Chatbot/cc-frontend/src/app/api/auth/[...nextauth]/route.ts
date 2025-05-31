import NextAuth, { NextAuthOptions } from "next-auth";
import GithubProvider from "next-auth/providers/github";
import GoogleProvider from "next-auth/providers/google";
import AzureADProvider from "next-auth/providers/azure-ad";
import { NextRequest, NextResponse } from "next/server";

const authOptions: NextAuthOptions = {
  providers: [
    GithubProvider({
      clientId: process.env.GITHUB_ID!,
      clientSecret: process.env.GITHUB_SECRET!,
    }),
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
    AzureADProvider({
      clientId: process.env.AZURE_AD_CLIENT_ID!,
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
      tenantId: process.env.AZURE_AD_TENANT_ID!,
    }),
    // Add more providers here
  ],
  secret: process.env.NEXTAUTH_SECRET,
  // Add more NextAuth options here (callbacks, pages, etc.)
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
// Be sure to add the following to your .env.local:
// NEXTAUTH_SECRET=your-secret-key-here
// GITHUB_ID=...
// GITHUB_SECRET=...
// GOOGLE_CLIENT_ID=...
// GOOGLE_CLIENT_SECRET=...
// AZURE_AD_CLIENT_ID=...
// AZURE_AD_CLIENT_SECRET=...
// AZURE_AD_TENANT_ID=... 