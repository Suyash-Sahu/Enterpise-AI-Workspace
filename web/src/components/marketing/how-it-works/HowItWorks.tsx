import { Container } from "@/components/shared";
import SectionTitle from "./SectionTitle";
import ProcessFlow from "./ProcessFlow";

export default function HowItWorks({ surface = false }: { surface?: boolean }) {
    return (
        <section
            id="how-it-works"
            className={`overflow-hidden py-16 md:py-24 ${
                surface ? "bg-surface" : "bg-background"
            }`}
        >
            <Container>
                <SectionTitle />
                <ProcessFlow />
            </Container>
        </section>
    );
}
