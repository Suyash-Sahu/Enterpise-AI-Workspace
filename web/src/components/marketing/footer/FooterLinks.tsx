import Link from "next/link";

export default function FooterLinks() {
    const sections = [
        {
            title: "Product",
            links: [
                { label: "AMOF Architecture", href: "#how-it-works" },
                { label: "Features", href: "#features" },
                { label: "AI Agents", href: "#agents" },
                { label: "Integrations", href: "#integrations" },
                { label: "Hybrid Execution", href: "#execution" },
            ],
        },
        {
            title: "Enterprise",
            links: [
                { label: "Security & Governance", href: "#security" },
                { label: "Use Cases", href: "#use-cases" },
                { label: "Pricing Tiers", href: "#pricing" },
                { label: "Interactive Screenshots", href: "#screenshots" },
                { label: "FAQ", href: "#faq" },
            ],
        },
        {
            title: "Connectors",
            links: [
                { label: "Gmail Adapter", href: "#integrations" },
                { label: "Google Drive Sync", href: "#integrations" },
                { label: "Text-to-SQL DB Agent", href: "#integrations" },
                { label: "Slack & Jira", href: "#integrations" },
                { label: "Local Files", href: "#integrations" },
            ],
        },
    ];

    return (
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-3">
            {sections.map((sec, idx) => (
                <div key={idx}>
                    <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-foreground">
                        {sec.title}
                    </h4>
                    <ul className="mt-4 space-y-2.5">
                        {sec.links.map((link, lIdx) => (
                            <li key={lIdx}>
                                <Link
                                    href={link.href}
                                    className="text-xs text-muted-foreground transition-colors hover:text-foreground"
                                >
                                    {link.label}
                                </Link>
                            </li>
                        ))}
                    </ul>
                </div>
            ))}
        </div>
    );
}
