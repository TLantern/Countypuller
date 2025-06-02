import { NextAuthOptions } from "next-auth";
import GithubProvider from "next-auth/providers/github";
import GoogleProvider from "next-auth/providers/google";
import AzureADProvider from "next-auth/providers/azure-ad";
import CredentialsProvider from "next-auth/providers/credentials";
import { PrismaAdapter } from "@next-auth/prisma-adapter";
import bcrypt from 'bcryptjs';
import prisma from '../../../../lib/prisma';

const authOptions: NextAuthOptions = {
  // Temporarily disable adapter to test JWT strategy
  // adapter: PrismaAdapter(prisma),
  session: {
    strategy: "jwt", // Switch to JWT strategy temporarily
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  pages: {
    signIn: '/login',
    signOut: '/login',
    error: '/login', // Error code passed in query string as ?error=
  },
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
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        console.log('Credentials authorize called with:', { email: credentials?.email });
        if (!credentials?.email || !credentials?.password) return null;
        
        try {
          const user = await prisma.user.findUnique({ where: { email: credentials.email } });
          console.log('User found:', user ? { id: user.id, email: user.email } : 'No user found');
          
          if (!user) return null;
          const isValid = await bcrypt.compare(credentials.password, user.password);
          console.log('Password valid:', isValid);
          
          if (!isValid) return null;
          return { id: user.id, email: user.email, name: user.firstName };
        } catch (error) {
          console.error('Auth error:', error);
          return null;
        }
      }
    }),
    // Add more providers here
  ],
  secret: process.env.NEXTAUTH_SECRET || "10749645e8d2e267f4f15bb9b8cb2f38b352913e11db666d3d5cf858933237f1",
  callbacks: {
    async signIn({ user, account, profile }) {
      console.log('SignIn callback triggered:', { user, account: account?.provider });
      
      // Handle OAuth providers (Google, GitHub, Azure)
      if (account && account.provider !== 'credentials') {
        try {
          // Check if user already exists in database by email
          let dbUser = await prisma.user.findUnique({
            where: { email: user.email! }
          });
          
          if (!dbUser) {
            // Create new user in database for OAuth users
            console.log('Creating new OAuth user in database:', user.email);
            dbUser = await prisma.user.create({
              data: {
                email: user.email!,
                firstName: user.name || 'OAuth User',
                lastName: '',
                password: '', // OAuth users don't have password
                createdAt: new Date(),
              }
            });
            console.log('✅ Created OAuth user with UUID:', dbUser.id);
          } else {
            console.log('✅ Found existing OAuth user:', dbUser.id);
          }
          
          // Update user.id with database UUID for JWT token
          user.id = dbUser.id;
          
        } catch (error) {
          console.error('❌ Error creating/finding OAuth user:', error);
          return false; // Deny sign in on error
        }
      }
      
      return true; // Allow sign in
    },
    async jwt({ token, user }) {
      // Store user id in JWT token
      if (user) {
        token.userId = user.id;
      }
      return token;
    },
    async session({ session, token }) {
      // Add user id to session from JWT token
      if (session.user && token) {
        (session.user as any).id = token.userId;
      }
      console.log('Session callback result:', session);
      return session;
    },
    async redirect({ url, baseUrl }) {
      console.log('Redirect callback:', { url, baseUrl });
      // Allows relative callback URLs
      if (url.startsWith("/")) return `${baseUrl}${url}`;
      // Allows callback URLs on the same origin
      else if (new URL(url).origin === baseUrl) return url;
      return `${baseUrl}/dashboard`;
    },
  },
  debug: true, // Enable debug mode
  // Add more NextAuth options here (callbacks, pages, etc.)
};

export { authOptions }; 