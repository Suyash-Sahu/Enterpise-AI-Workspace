import { ShieldCheck, Lock, Cpu } from "lucide-react";

const ITEMS = [
    { icon: ShieldCheck, text: "Enterprise security" },
    { icon: Lock, text: "Privacy-first, local execution" },
    { icon: Cpu, text: "Hybrid local + cloud AI" },
];

/**
 * Thin trust strip shown just below the hero — kept out of the hero itself so
 * the fold stays to headline + subline + actions + product shot.
 */
export default function HeroTrust() {
    return (
        <div className="border-b border-border bg-surface">
            <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-center gap-x-10 gap-y-3 px-6 py-5 lg:px-8">
                {ITEMS.map(({ icon: Icon, text }) => (
                    <div
                        key={text}
                        className="flex items-center gap-2 text-sm text-muted-foreground"
                    >
                        <Icon className="h-4 w-4 text-primary" aria-hidden />
                        {text}
                    </div>
                ))}
            </div>
        </div>
    );
}
