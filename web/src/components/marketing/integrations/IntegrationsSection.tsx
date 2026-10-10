"use client";

import { useState } from "react";
import { Container } from "@/components/shared";
import IntegrationCategory from "./IntegrationCategory";
import IntegrationGrid from "./IntegrationGrid";
import { INTEGRATIONS } from "./integrationsData";
import { Workflow } from "lucide-react";

export default function IntegrationsSection({ surface = false }: { surface?: boolean }) {
    const [activeCategory, setActiveCategory] = useState<string>("all");

    const filteredIntegrations = activeCategory === "all"
        ? INTEGRATIONS
        : INTEGRATIONS.filter((i) => i.category === activeCategory);

    return (
        <section
            id="integrations"
            className={`overflow-hidden py-16 md:py-24 ${
                surface ? "bg-surface" : "bg-background"
            }`}
        >
            <Container>
                <div className="mx-auto max-w-2xl text-center">
                    <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                        <Workflow className="h-3.5 w-3.5" aria-hidden />
                        <span>Unified connector manager</span>
                    </div>

                    <h2 className="mt-5 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
                        Connect every enterprise tool{" "}
                        <span className="text-primary">without credential risk</span>
                    </h2>

                    <p className="mt-4 text-base leading-relaxed text-muted-foreground">
                        The connector manager talks to your existing OAuth accounts — Gmail, Google Drive, Microsoft 365, Slack, Jira, and SQL databases — so no passwords or secret keys are ever stored on our servers.
                    </p>
                </div>

                <IntegrationCategory activeCategory={activeCategory} onSelect={setActiveCategory} />

                <IntegrationGrid integrations={filteredIntegrations} />
            </Container>
        </section>
    );
}
