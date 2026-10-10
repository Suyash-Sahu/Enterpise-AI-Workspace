"use client";

import { useSessionContext } from "@/providers/session-provider";

export function useCurrentUser() {
  const { user, status, logout, refetchSession } = useSessionContext();

  return {
    user,
    status,
    isAuthenticated: status === "authenticated",
    isLoading: status === "loading",
    logout,
    refetchSession,
  };
}

export default useCurrentUser;
