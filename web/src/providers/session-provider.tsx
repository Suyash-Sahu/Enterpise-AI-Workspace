"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { User, AuthState } from "@/types/auth";
import { LOGOUT_URL, getCurrentUser } from "@/services/auth.service";

const SessionContext = createContext<AuthState | undefined>(undefined);

/**
 * Resolves the signed-in user from the server.
 *
 * This previously seeded a hardcoded "Alex Dev" user and reported
 * "authenticated" unconditionally — including from the catch block — which
 * made ProtectedRoute inert for every workspace route. Status now reflects
 * what the server actually says.
 */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<
    "loading" | "authenticated" | "unauthenticated"
  >("loading");

  const fetchSession = useCallback(async () => {
    // Asks the backend directly. There is no Next-side session to consult,
    // and no token to warm — the cookie travels on its own.
    const current = await getCurrentUser();

    if (current) {
      setUser(current);
      setStatus("authenticated");
    } else {
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      // The backend revokes the session server-side and clears the cookies;
      // there is no client-held credential left to discard.
      await fetch(LOGOUT_URL, {
        method: "POST",
        credentials: "same-origin",
      });
    } catch {
      // Revocation failed; still drop local state below.
    }

    setUser(null);
    setStatus("unauthenticated");
    window.location.href = "/login";
  }, []);

  useEffect(() => {
    void fetchSession();
  }, [fetchSession]);

  return (
    <SessionContext.Provider
      value={{
        user,
        status,
        logout,
        refetchSession: fetchSession,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSessionContext() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSessionContext must be used within a SessionProvider");
  }
  return context;
}
