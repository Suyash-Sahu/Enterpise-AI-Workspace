"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { User as UserIcon, LayoutDashboard, Settings, ChevronDown } from "lucide-react";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { LogoutButton } from "./logout-button";

export function UserMenu() {
  const { user, isAuthenticated, isLoading } = useCurrentUser();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (isLoading) {
    return <div className="h-9 w-9 animate-pulse rounded-full bg-zinc-800" />;
  }

  if (!isAuthenticated || !user) {
    return (
      <Link
        href="/login"
        className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-md transition-all hover:bg-primary active:scale-95"
      >
        Sign In
      </Link>
    );
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2.5 rounded-full border border-white/10 bg-white/5 p-1.5 pr-3 text-left transition-all hover:border-white/20 hover:bg-white/10 focus:outline-none"
      >
        {user.picture ? (
          <Image
            src={user.picture}
            alt={user.name || "User Avatar"}
            width={32}
            height={32}
            className="h-8 w-8 rounded-full object-cover ring-2 ring-indigo-500/30"
          />
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-bold text-white">
            {user.name ? user.name.charAt(0).toUpperCase() : <UserIcon className="h-4 w-4" />}
          </div>
        )}
        <span className="max-w-[120px] truncate text-sm font-medium text-zinc-200">
          {user.name || user.email}
        </span>
        <ChevronDown className={`h-4 w-4 text-zinc-400 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 rounded-2xl border border-white/10 bg-zinc-900/95 p-2 shadow-md backdrop-blur-xl animate-in fade-in zoom-in-95 duration-150 z-50">
          {/* User Details Header */}
          <div className="flex items-center gap-3 border-b border-white/10 px-3 py-3">
            {user.picture ? (
              <Image
                src={user.picture}
                alt={user.name}
                width={40}
                height={40}
                className="h-10 w-10 rounded-full object-cover ring-2 ring-indigo-500/40"
              />
            ) : (
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary font-bold text-white">
                {user.name ? user.name.charAt(0).toUpperCase() : "U"}
              </div>
            )}
            <div className="flex flex-col min-w-0">
              <p className="truncate text-sm font-semibold text-white">{user.name}</p>
              <p className="truncate text-xs text-zinc-400">{user.email}</p>
            </div>
          </div>

          {/* Quick Menu Links */}
          <div className="py-2 space-y-1">
            <Link
              href="/dashboard"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-zinc-300 hover:bg-white/10 hover:text-white transition-colors"
            >
              <LayoutDashboard className="h-4 w-4 text-primary" />
              <span>Dashboard</span>
            </Link>
            <Link
              href="/dashboard"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-zinc-300 hover:bg-white/10 hover:text-white transition-colors"
            >
              <Settings className="h-4 w-4 text-success" />
              <span>Settings</span>
            </Link>
          </div>

          {/* Sign Out Button */}
          <div className="border-t border-white/10 pt-2">
            <LogoutButton variant="danger" className="w-full justify-start">
              Sign Out
            </LogoutButton>
          </div>
        </div>
      )}
    </div>
  );
}

export default UserMenu;
