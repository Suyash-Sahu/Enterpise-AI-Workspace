"use client";

import Link from "next/link";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import UserMenu from "@/components/auth/user-menu";
import { Button } from "@/components/ui/button";

export default function CTAButtons() {
  const { isAuthenticated, isLoading } = useCurrentUser();

  if (isLoading) {
    return <div className="h-9 w-24 animate-pulse rounded-sm bg-muted" />;
  }

  if (isAuthenticated) {
    return <UserMenu />;
  }

  return (
    <div className="flex items-center gap-2">
      <Button variant="ghost" asChild>
        <Link href="/login">Sign in</Link>
      </Button>

      <Button asChild>
        <Link href="/login">Get started</Link>
      </Button>
    </div>
  );
}
