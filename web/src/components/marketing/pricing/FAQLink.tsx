import Link from "next/link";
import { HelpCircle, ArrowRight } from "lucide-react";

export default function FAQLink() {
    return (
        <div className="mt-12 text-center">
            <p className="text-xs text-muted-foreground">
                Have custom compliance, volume licensing, or air-gapped deployment questions?
            </p>
            <Link
                href="#faq"
                className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline"
            >
                <HelpCircle className="h-3.5 w-3.5" />
                <span>Read our Enterprise FAQ</span>
                <ArrowRight className="h-3 w-3" />
            </Link>
        </div>
    );
}
