import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function HeroActions() {
    return (
        <div className="mt-8 flex flex-wrap items-center gap-3">
            <Button size="lg" asChild>
                <Link href="/onboarding">
                    Get started
                    <ArrowRight aria-hidden />
                </Link>
            </Button>

            <Button size="lg" variant="ghost" asChild>
                <Link href="#how-it-works">See how it works</Link>
            </Button>
        </div>
    );
}
