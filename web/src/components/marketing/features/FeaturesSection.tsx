"use client";

import { useState } from "react";
import { Container } from "@/components/shared";
import FeatureTabs from "./FeatureTabs";
import FeatureGrid from "./FeatureGrid";
import FeaturePreview from "./FeaturePreview";
import FeatureCTA from "./FeatureCTA";
import { FEATURES } from "./featuresData";
import { Cpu } from "lucide-react";

export default function FeaturesSection({ surface = false }: { surface?: boolean }) {
    const [activeCategory, setActiveCategory] = useState<string>("all");

    const filteredFeatures = activeCategory === "all"
        ? FEATURES
        : FEATURES.filter((f) => f.category === activeCategory);

    return (
        <section
            id="features"
            className={`overflow-hidden py-16 md:py-24 ${
                surface ? "bg-surface" : "bg-background"
            }`}
        >
            <Container>
                <div className="mx-auto max-w-2xl text-center">
                    <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                        <Cpu className="h-3.5 w-3.5" aria-hidden />
                        <span>Platform capabilities</span>
                    </div>

                    <h2 className="mt-5 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
                        Engineered for{" "}
                        <span className="text-primary">
                            enterprise performance and security
                        </span>
                    </h2>

                    <p className="mt-4 text-base leading-relaxed text-muted-foreground">
                        Everything you need to orchestrate complex workflows across disconnected SaaS tools while keeping your proprietary data private and secure.
                    </p>
                </div>

                <FeatureTabs activeCategory={activeCategory} onSelect={setActiveCategory} />

                <FeatureGrid features={filteredFeatures} />

                <FeaturePreview />

                <FeatureCTA />
            </Container>
        </section>
    );
}
