import { Container } from "@/components/shared";
import CTAButtons from "./CTAButtons";
import CTAStats from "./CTAStats";
import { ShieldCheck } from "lucide-react";

export default function CTA() {
    return (
        <section className="overflow-hidden bg-background py-16 md:py-24">
            <Container>
                <div className="mx-auto max-w-3xl rounded-md border border-border bg-surface p-8 text-center shadow-sm sm:p-12">
                    <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                        <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
                        <span>Ready for production</span>
                    </div>

                    <h2 className="mx-auto mt-5 max-w-2xl text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
                        Bring every enterprise tool into one conversation
                    </h2>

                    <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
                        Stop switching context between a dozen tools. Unified natural-language orchestration, with privacy and a human approval gate built in.
                    </p>

                    <CTAButtons />

                    <CTAStats />
                </div>
            </Container>
        </section>
    );
}
