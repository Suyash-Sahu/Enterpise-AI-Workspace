import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";

export default function FeatureCTA() {
    return (
        <div className="mt-16 text-center">
            <div className="inline-flex flex-col sm:flex-row items-center gap-4 rounded-2xl border border-primary/20 bg-primary/5 p-6 backdrop-blur-md">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shrink-0 shadow-lg">
                    <Sparkles className="h-6 w-6" />
                </div>
                <div className="text-left">
                    <h4 className="text-base font-bold text-foreground">Ready to deploy AMOF in your organization?</h4>
                    <p className="text-xs text-muted-foreground">Experience full enterprise privacy and multi-agent coordination today.</p>
                </div>
                <Link
                    href="/dashboard"
                    className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-xs font-semibold text-primary-foreground shadow-md transition-transform hover:scale-105"
                >
                    <span>Launch Workspace</span>
                    <ArrowRight className="h-4 w-4" />
                </Link>
            </div>
        </div>
    );
}
