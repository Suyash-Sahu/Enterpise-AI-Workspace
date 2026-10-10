import { Container } from "@/components/shared";
import Logo from "@/components/shared/Logo";
import FooterLinks from "@/components/marketing/footer/FooterLinks";
import FooterSocials from "@/components/marketing/footer/FooterSocials";
import FooterNewsletter from "@/components/marketing/footer/FooterNewsletter";

const LEGAL = ["Privacy Policy", "Terms of Service", "Security Portal"];

export default function Footer() {
    return (
        <footer className="border-t border-border bg-background pb-12 pt-16">
            <Container className="space-y-12">
                <div className="grid grid-cols-1 gap-12 lg:grid-cols-12">
                    <div className="space-y-4 lg:col-span-4">
                        <Logo />
                        <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">
                            A hybrid desktop AI platform that unifies enterprise data across
                            Gmail, Drive, databases, and SaaS tools with multi-agent
                            orchestration and local-first security.
                        </p>
                        <FooterSocials />
                    </div>

                    <div className="lg:col-span-5">
                        <FooterLinks />
                    </div>

                    <div className="lg:col-span-3">
                        <FooterNewsletter />
                    </div>
                </div>

                <div className="flex flex-col items-center justify-between gap-4 border-t border-border pt-8 text-xs text-muted-foreground sm:flex-row">
                    <p>
                        © {new Date().getFullYear()} Enterprise AI Workspace (AMOF Edition).
                        All rights reserved.
                    </p>
                    <ul className="flex items-center gap-6">
                        {LEGAL.map((item) => (
                            <li key={item}>
                                <a
                                    href="#"
                                    className="rounded-sm transition-colors hover:text-foreground"
                                >
                                    {item}
                                </a>
                            </li>
                        ))}
                    </ul>
                </div>
            </Container>
        </footer>
    );
}
