"use client";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { signIn, signOut, useSession } from "next-auth/react";

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
    case "apple":
      return (
        <svg className="h-5 w-5 mr-2" viewBox="0 0 24 24" fill="currentColor"><path d="M16.365 1.43c0 1.14-.93 2.07-2.07 2.07s-2.07-.93-2.07-2.07.93-2.07 2.07-2.07 2.07.93 2.07 2.07zm4.13 6.13c-.09-.09-.19-.17-.29-.25-.1-.08-.21-.15-.32-.21-.11-.06-.23-.11-.35-.15-.12-.04-.25-.07-.38-.09-.13-.02-.27-.03-.41-.03-.14 0-.28.01-.41.03-.13.02-.26.05-.38.09-.12.04-.24.09-.35.15-.11.06-.22.13-.32.21-.1.08-.2.16-.29.25-.09.09-.17.19-.25.29-.08.1-.15.21-.21.32-.06.11-.11.23-.15.35-.04.12-.07.25-.09.38-.02.13-.03.27-.03.41 0 .14.01.28.03.41.02.13.05.26.09.38.04.12.09.24.15.35.06.11.13.22.21.32.08.1.16.2.25.29.09.09.19.17.29.25.1.08.21.15.32.21.11.06.23.11.35.15.12.04.25.07.38.09.13.02.27.03.41.03.14 0 .28-.01.41-.03.13-.02.26-.05.38-.09.12-.04.24-.09.35-.15.11-.06.22-.13.32-.21.1-.08.2-.16.29-.25.09-.09.17-.19.25-.29.08-.1.15-.21.21-.32.06-.11.11-.23.15-.35.04-.12.07-.25.09-.38.02-.13.03-.27.03-.41 0-.14-.01-.28-.03-.41-.02-.13-.05-.26-.09-.38-.04-.12-.09-.24-.15-.35-.06-.11-.13-.22-.21-.32-.08-.1-.16-.2-.25-.29z"/></svg>
      );
    case "azure-ad":
      return (
        <svg className="h-5 w-5 mr-2" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10" fill="#0078D4"/><path d="M12 6v6l4 2" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
      );
    default:
      return null;
  }
}

export function LoginForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const { data: session, status } = useSession();

  if (status === "loading") {
    return <div>Loading...</div>;
  }

  if (session) {
    return (
      <div className={cn("flex flex-col gap-6", className)} {...props}>
        <div>Signed in as {session.user?.email}</div>
        <Button onClick={() => signOut()} className="w-full">
          Sign out
        </Button>
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <Card>
        <CardHeader className="text-center">
          <CardTitle className="text-xl">Welcome back</CardTitle>
          <CardDescription>
            Login with your account
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3">
            <Button
              variant="outline"
              className="w-full flex items-center justify-center"
              onClick={() => signIn("github")}
            >
              <ProviderIcon provider="github" />
              Sign in with GitHub
            </Button>
            <Button
              variant="outline"
              className="w-full flex items-center justify-center"
              onClick={() => signIn("google")}
            >
              <ProviderIcon provider="google" />
              Sign in with Google
            </Button>
            <Button
              variant="outline"
              className="w-full flex items-center justify-center"
              onClick={() => signIn("apple")}
            >
              <ProviderIcon provider="apple" />
              Sign in with Apple
            </Button>
            <Button
              variant="outline"
              className="w-full flex items-center justify-center"
              onClick={() => signIn("azure-ad")}
            >
              <ProviderIcon provider="azure-ad" />
              Sign in with Microsoft
            </Button>
          </div>
          <div className="text-center text-sm mt-4">
            Don&apos;t have an account?{" "}
            <a href="/api/auth/signin" className="underline underline-offset-4">
              Sign up
            </a>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}