import { Container } from "@/components/shared";
import FAQAccordion from "./FAQAccordion";
import { HelpCircle } from "lucide-react";

export default function FAQSection({ surface = false }: { surface?: boolean }) {
    return (
        <section
            id="faq"
            className={`overflow-hidden py-16 md:py-24 ${
                surface ? "bg-surface" : "bg-background"
            }`}
        >
            <Container>
                <div className="mx-auto max-w-2xl text-center">
                    <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                        <HelpCircle className="h-3.5 w-3.5" aria-hidden />
                        <span>Frequently asked questions</span>
                    </div>

                    <h2 className="mt-5 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
                        Everything you need to know
                    </h2>

                    <p className="mt-4 text-base leading-relaxed text-muted-foreground">
                        Questions about local mode, OAuth integrations, or model routing — answered.
                    </p>
                </div>

                <FAQAccordion />
            </Container>
        </section>
    );
}
