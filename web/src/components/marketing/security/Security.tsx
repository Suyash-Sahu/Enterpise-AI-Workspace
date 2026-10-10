"use client";

import { Container } from "@/components/shared";
import SecurityCard from "./SecurityCard";
import ComplianceGrid from "./ComplianceGrid";
import SecurityDiagram from "./SecurityDiagram";
import SecurityStats from "./SecurityStats";
import { ShieldCheck, Lock, Key, UserCheck } from "lucide-react";

export default function Security({ surface = false }: { surface?: boolean }) {
    return (
        <section
            id="security"
            className={`overflow-hidden py-16 md:py-24 ${
                surface ? "bg-surface" : "bg-background"
            }`}
        >
            <Container>
                <div className="mx-auto max-w-2xl text-center">
                    <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                        <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
                        <span>Enterprise governance and privacy</span>
                    </div>

                    <h2 className="mt-5 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
                        Built for security teams,{" "}
                        <span className="text-primary">trusted by IT admins</span>
                    </h2>

                    <p className="mt-4 text-base leading-relaxed text-muted-foreground">
                        A zero-trust connector model and local-first execution keep sensitive data within your boundary.
                    </p>
                </div>

                <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                    <SecurityCard
                        title="Zero-Trust Credential Isolation"
                        badge="Connector Manager"
                        icon={Lock}
                        description="All integrations use scoped OAuth tokens directly with your cloud accounts. Raw passwords and master keys are never stored."
                        points={["Scoped Gmail & Drive access", "OAuth token refreshing", "No credential persistence"]}
                    />

                    <SecurityCard
                        title="Human Approval Gating"
                        badge="Governance"
                        icon={UserCheck}
                        description="Every external side-effect—sending an email, modifying a database, or creating a ticket—requires human verification."
                        points={["Explicit UI confirmation", "Inline message editing", "Immutable approval logs"]}
                    />

                    <SecurityCard
                        title="Local Key & Vector Storage"
                        badge="On-Device Security"
                        icon={Key}
                        description="API keys and local vector embeddings are stored in encrypted OS keychain vaults on your local machine."
                        points={["AES-256 local keychain", "Air-gapped RAG vector store", "Zero third-party training"]}
                    />
                </div>

                <ComplianceGrid />

                <SecurityDiagram />

                <SecurityStats />
            </Container>
        </section>
    );
}
