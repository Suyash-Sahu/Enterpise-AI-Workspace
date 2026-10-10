import Link from "next/link";
import { ArrowRight, Download, Sparkles } from "lucide-react";

export default function CTAButtons() {
    return (
        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
                href="/dashboard"
                className="inline-flex h-12 w-full sm:w-auto items-center justify-center gap-2 rounded-xl bg-primary px-6 text-sm font-semibold text-primary-foreground shadow-lg transition-transform hover:scale-105"
            >
                <Sparkles className="h-4 w-4" />
                <span>Launch Enterprise Workspace</span>
                <ArrowRight className="h-4 w-4" />
            </Link>

            <Link
                href="#how-it-works"
                className="inline-flex h-12 w-full sm:w-auto items-center justify-center gap-2 rounded-xl border border-border bg-background px-6 text-sm font-semibold text-foreground hover:border-primary/40 hover:bg-muted/50 transition-all"
            >
                <Download className="h-4 w-4 text-muted-foreground" />
                <span>Download Desktop App</span>
            </Link>
        </div>
    );
}
