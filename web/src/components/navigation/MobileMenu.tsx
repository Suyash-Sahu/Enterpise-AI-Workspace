"use client";

import Link from "next/link";
import { Menu } from "lucide-react";

import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { MARKETING_NAV } from "@/constants/navigation";

export default function MobileMenu() {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu">
          <Menu aria-hidden />
        </Button>
      </SheetTrigger>

      <SheetContent side="right" className="w-72 sm:max-w-72">
        <SheetTitle className="px-1 text-sm font-semibold">Menu</SheetTitle>
        <nav className="mt-2 flex flex-col">
          {MARKETING_NAV.map((item) => (
            <SheetClose asChild key={item.label}>
              <Link
                href={item.href}
                className="rounded-sm px-1 py-2.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                {item.label}
              </Link>
            </SheetClose>
          ))}
        </nav>
      </SheetContent>
    </Sheet>
  );
}
