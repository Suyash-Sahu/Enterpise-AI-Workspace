"use client";

import { useState } from "react";
import { Container } from "@/components/shared";
import PricingCard, { Plan } from "./PricingCard";
import ComparisonTable from "./ComparisonTable";
import FAQLink from "./FAQLink";
import { DollarSign } from "lucide-react";

const PLANS: Plan[] = [
    {
        id: "starter",
        name: "Starter",
        badge: "Free Local Tier",
        price: "$0",
        period: "forever / free",
        description: "Perfect for individual knowledge workers running local Ollama models on desktop.",
        features: [
            "Full AMOF Desktop App",
            "Unlimited Local Mode runs",
            "Gmail & Drive OAuth connectors",
            "Human Approval Gate",
            "Standard community support",
        ],
        ctaText: "Download Workspace",
        ctaHref: "/dashboard",
    },
    {
        id: "team",
        name: "Team",
        badge: "Recommended",
        popular: true,
        price: "$29",
        period: "per user / month",
        description: "Designed for collaborative teams requiring hybrid local + cloud model routing.",
        features: [
            "Everything in Starter",
            "AI Execution Manager Hybrid Mode",
            "Text-to-SQL DB Connectors",
            "Shared team memory layer",
            "30-day token observability logs",
            "Priority email & chat support",
        ],
        ctaText: "Start 14-Day Free Trial",
        ctaHref: "/dashboard",
    },
    {
        id: "enterprise",
        name: "Enterprise",
        badge: "Custom Cloud / On-Prem",
        price: "Custom",
        period: "contact sales",
        description: "For organizations demanding strict RBAC, custom LLM fine-tuning, and SLA guarantees.",
        features: [
            "Everything in Team",
            "Dedicated VPC / On-Prem deployment",
            "Custom local model fine-tuning",
            "Unlimited audit log exports",
            "Enterprise SSO & SAML / Okta",
            "24/7 dedicated solution engineer",
        ],
        ctaText: "Contact Enterprise Sales",
        ctaHref: "/contact",
    },
];

export default function Pricing({ surface = false }: { surface?: boolean }) {
    const [billingCycle, setBillingCycle] = useState<"monthly" | "annual">("annual");

    return (
        <section
            id="pricing"
            className={`overflow-hidden py-16 md:py-24 ${
                surface ? "bg-surface" : "bg-background"
            }`}
        >
            <Container>
                <div className="mx-auto max-w-2xl text-center">
                    <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                        <DollarSign className="h-3.5 w-3.5" aria-hidden />
                        <span>Predictable pricing</span>
                    </div>

                    <h2 className="mt-5 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
                        Simple plans for teams of any size,{" "}
                        <span className="text-primary">zero hidden fees</span>
                    </h2>

                    <p className="mt-4 text-base leading-relaxed text-muted-foreground">
                        Start free with local desktop execution, or unlock team collaboration and cloud reasoning as you grow.
                    </p>

                    <div className="mt-8 flex items-center justify-center gap-3">
                        <span className={`text-xs font-semibold ${billingCycle === "monthly" ? "text-foreground" : "text-muted-foreground"}`}>
                            Monthly Billing
                        </span>
                        <button
                            onClick={() => setBillingCycle(billingCycle === "monthly" ? "annual" : "monthly")}
                            className="relative flex h-6 w-11 items-center rounded-full bg-primary/20 p-1 transition-colors"
                        >
                            <span
                                className={`h-4 w-4 rounded-full bg-primary transition-transform ${
                                    billingCycle === "annual" ? "translate-x-5" : "translate-x-0"
                                }`}
                            />
                        </button>
                        <span className={`text-xs font-semibold ${billingCycle === "annual" ? "text-foreground" : "text-muted-foreground"}`}>
                            Annual Billing <span className="rounded-full bg-success/10 px-2 py-0.5 text-xs text-success font-mono">Save 20%</span>
                        </span>
                    </div>
                </div>

                <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3">
                    {PLANS.map((plan) => (
                        <PricingCard key={plan.id} plan={plan} />
                    ))}
                </div>

                <ComparisonTable />

                <FAQLink />
            </Container>
        </section>
    );
}
