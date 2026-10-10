"use client";

import React, { useState } from "react";

import { SIGN_IN_URL } from "@/services/auth.service";

interface GoogleSignInButtonProps {
  className?: string;
  label?: string;
}

export function GoogleSignInButton({
  className = "",
  label = "Sign in with Google",
}: GoogleSignInButtonProps) {
  const [isLoading, setIsLoading] = useState(false);

  const handleClick = () => {
    setIsLoading(true);
    // The backend owns this round trip: it mints the state and PKCE verifier,
    // redirects to Google, and sets the session cookies on the way back.
    // Connecting Gmail/Drive is a separate, broader-scoped consent later on
    // (see googleService.startGoogleConnect).
    window.location.href = SIGN_IN_URL;
  };

  return (
    <button
      onClick={handleClick}
      disabled={isLoading}
      className={`group relative flex w-full items-center justify-center gap-3 rounded-xl border border-white/10 bg-white/5 px-6 py-3.5 text-sm font-medium text-white shadow-lg backdrop-blur-md transition-all duration-300 hover:border-white/25 hover:bg-white/10 hover:shadow-indigo-500/10 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-70 ${className}`}
    >
      {isLoading ? (
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      ) : (
        <svg className="h-5 w-5 transition-transform duration-300 group-hover:scale-110" viewBox="0 0 24 24">
          <path
            fill="#EA4335"
            d="M12 5c1.6 0 3 .6 4.1 1.6l3.1-3.1C17.3 1.7 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.1 9 5 12 5z"
          />
          <path
            fill="#4285F4"
            d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.8z"
          />
          <path
            fill="#FBBC05"
            d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.3s.2-1.6.4-2.3L1.9 7.3C.7 9.7 0 12.4 0 15.3c0 2.9.7 5.6 1.9 8l3.7-2.9z"
          />
          <path
            fill="#34A853"
            d="M12 23c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.1-6.4-5.2L1.9 16C3.7 19.7 7.5 23 12 23z"
          />
        </svg>
      )}
      <span>{isLoading ? "Connecting to Google..." : label}</span>
    </button>
  );
}

export default GoogleSignInButton;
