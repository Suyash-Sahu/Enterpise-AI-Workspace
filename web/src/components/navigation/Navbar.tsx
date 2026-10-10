import Link from "next/link";

import { Container } from "@/components/shared";
import Logo from "@/components/shared/Logo";
import ThemeToggle from "@/components/ui/ThemeToggle";

import CTAButtons from "./CTAButtons";
import MobileMenu from "./MobileMenu";
import NavLinks from "./NavLinks";

export default function Navbar() {
    return (
        <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
            <Container className="flex h-16 items-center justify-between gap-4">
                <Link href="/" className="rounded-sm">
                    <Logo />
                </Link>

                <NavLinks />

                <div className="flex items-center gap-2">
                    <ThemeToggle />
                    <CTAButtons />
                    <MobileMenu />
                </div>
            </Container>
        </header>
    );
}
