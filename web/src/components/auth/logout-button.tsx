"use client";

import React, { useState } from "react";
import { LogOut } from "lucide-react";
import { useCurrentUser } from "@/hooks/useCurrentUser";

interface LogoutButtonProps {
  className?: string;
  variant?: "primary" | "ghost" | "danger";
  children?: React.ReactNode;
}

export function LogoutButton({
  className = "",
  variant = "ghost",
  children,
}: LogoutButtonProps) {
  const { logout } = useCurrentUser();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    await logout();
  };

  const baseStyles =
    "flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 active:scale-[0.97] disabled:opacity-50";

  const variantStyles = {
    primary: "bg-primary hover:bg-primary text-white shadow-md",
    ghost: "bg-white/5 hover:bg-white/10 text-zinc-300 hover:text-white border border-white/10",
    danger: "bg-destructive/10 hover:bg-destructive/20 text-destructive hover:text-destructive border border-destructive/20",
  };

  return (
    <button
      onClick={handleLogout}
      disabled={isLoggingOut}
      className={`${baseStyles} ${variantStyles[variant]} ${className}`}
    >
      {isLoggingOut ? (
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      ) : (
        <LogOut className="h-4 w-4" />
      )}
      <span>{children || (isLoggingOut ? "Signing out..." : "Sign Out")}</span>
    </button>
  );
}

export default LogoutButton;
