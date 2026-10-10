import { Check, Sparkles, ArrowRight } from "lucide-react";
import Link from "next/link";

export interface Plan {
    id: string;
    name: string;
    badge?: string;
    price: string;
    period: string;
    description: string;
    popular?: boolean;
    features: string[];
    ctaText: string;
    ctaHref: string;
}

interface Props {
    plan: Plan;
}

export default function PricingCard({ plan }: Props) {
    return (
        <div className={`group relative flex flex-col justify-between rounded-2xl border p-6 backdrop-blur-sm transition-all duration-300 ${
            plan.popular
                ? "border-primary bg-primary/5 shadow-md ring-1 ring-primary"
                : "border-border bg-background/80 hover:border-primary/40 hover:shadow-md"
        }`}>
            {plan.popular && (
                <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-1 text-xs font-bold text-primary-foreground shadow-md">
                    Most Popular
                </div>
            )}

            <div>
                <div className="flex items-center justify-between">
                    <h3 className="text-xl font-bold text-foreground">{plan.name}</h3>
                    {plan.badge && (
                        <span className="rounded-full border border-primary/20 bg-primary/10 px-2.5 py-0.5 text-xs font-mono text-primary">
                            {plan.badge}
                        </span>
                    )}
                </div>

                <div className="mt-4 flex items-baseline gap-1">
                    <span className="text-4xl font-semibold tracking-tight text-foreground">{plan.price}</span>
                    <span className="text-xs text-muted-foreground">{plan.period}</span>
                </div>

                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                    {plan.description}
                </p>
            </div>

            <div className="mt-6 border-t border-border pt-4">
                <ul className="space-y-2.5">
                    {plan.features.map((f, idx) => (
                        <li key={idx} className="flex items-center gap-2 text-xs font-medium text-foreground/80">
                            <Check className="h-3.5 w-3.5 text-primary shrink-0" />
                            <span>{f}</span>
                        </li>
                    ))}
                </ul>

                <Link
                    href={plan.ctaHref}
                    className={`mt-6 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-xs font-semibold transition-all ${
                        plan.popular
                            ? "bg-primary text-primary-foreground shadow-md"
                            : "border border-border bg-background text-foreground hover:border-primary/40 hover:bg-muted/50"
                    }`}
                >
                    <span>{plan.ctaText}</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                </Link>
            </div>
        </div>
    );
}
