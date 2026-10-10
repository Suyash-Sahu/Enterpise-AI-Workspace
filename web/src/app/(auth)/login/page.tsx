"use client";

import React, { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ShieldCheck, Sparkles, Cpu, ArrowLeft } from "lucide-react";
import GoogleSignInButton from "@/components/auth/google-signin-button";

/**
 * Every `?error=` code the backend's Google sign-in can redirect back with
 * (see app/api/auth.py `_signin_failed`), in plain language. An unmapped code
 * still renders, with the raw value, rather than showing a blank box.
 */
const SIGN_IN_ERRORS: Record<string, string> = {
  auth_not_configured:
    "Google sign-in is not configured on the server. Check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
  missing_code: "Google sign-in was cancelled before it finished.",
  invalid_state:
    "That sign-in link expired or was already used. Please try signing in again.",
  token_exchange_failed:
    "Google refused the sign-in. Verify the redirect URI registered in Google Cloud matches this app.",
  userinfo_failed: "Could not read your Google profile. Please try again.",
  email_not_verified:
    "Your Google email address is not verified, so it cannot be used to sign in.",
  signin_failed: "Could not establish your account. Please try again.",
};

function LoginContent() {
  const searchParams = useSearchParams();
  const error = searchParams.get("error");

  return (
    <div className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-zinc-950 px-4 text-zinc-100">
      {/* Dynamic Background Gradients */}
      <div className="absolute -top-40 -left-40 h-96 w-96 rounded-full bg-primary/20 blur-[128px] pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-primary/20 blur-[128px] pointer-events-none" />

      {/* Back to Home Button */}
      <Link
        href="/"
        className="absolute top-6 left-6 flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-zinc-300 backdrop-blur-md transition-all hover:bg-white/10 hover:text-white"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to Home
      </Link>

      <div className="relative w-full max-w-md space-y-8 rounded-md border border-white/10 bg-zinc-900/60 p-8 shadow-md backdrop-blur-2xl">
        {/* Header Branding */}
        <div className="text-center space-y-3">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/20 border border-primary/30 text-primary">
            <Cpu className="h-6 w-6" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Welcome Back</h1>
          <p className="text-sm text-zinc-400">
            Sign in to access your Enterprise AI Multi-Agent Workspace
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div
            role="alert"
            className="rounded-xl border border-destructive/30 bg-destructive/10 p-3.5 text-center text-xs text-destructive"
          >
            {SIGN_IN_ERRORS[error] ?? `Sign-in failed (${error}). Please try again.`}
          </div>
        )}

        {/* Sign In Options */}
        <div className="space-y-4 pt-2">
          <GoogleSignInButton label="Continue with Google" />
          
          <p className="text-center text-xs text-zinc-500">
            By signing in, you agree to our Terms of Service & Privacy Policy.
          </p>
        </div>

        {/* Feature Badges */}
        <div className="grid grid-cols-2 gap-3 border-t border-white/10 pt-6">
          <div className="flex items-center gap-2 rounded-xl border border-white/5 bg-white/[0.02] p-3 text-xs text-zinc-400">
            <ShieldCheck className="h-4 w-4 text-success flex-shrink-0" />
            <span>Secure JWT Session</span>
          </div>
          <div className="flex items-center gap-2 rounded-xl border border-white/5 bg-white/[0.02] p-3 text-xs text-zinc-400">
            <Sparkles className="h-4 w-4 text-warning flex-shrink-0" />
            <span>OAuth 2.0 Auth</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-zinc-950 text-white">Loading...</div>}>
      <LoginContent />
    </Suspense>
  );
}
