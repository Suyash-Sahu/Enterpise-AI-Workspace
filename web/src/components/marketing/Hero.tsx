import { Container } from "@/components/shared";

import HeroBackground from "./HeroBackground";
import HeroContent from "./HeroContent";
import WorkspaceMockup from "./workspace/WorkspaceMockup";

export default function Hero() {
    return (
        <section className="relative overflow-hidden border-b border-border">
            <HeroBackground />

            <Container className="relative py-20 lg:py-28">
                <div className="grid items-center gap-14 lg:grid-cols-2">
                    <HeroContent />

                    <div className="hidden lg:block">
                        <WorkspaceMockup />
                    </div>
                </div>
            </Container>
        </section>
    );
}
