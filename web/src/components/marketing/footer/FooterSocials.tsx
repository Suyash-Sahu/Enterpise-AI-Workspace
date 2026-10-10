import Link from "next/link";
import { Globe, MessageCircle, Share2, Code2 } from "lucide-react";

export default function FooterSocials() {
    const socials = [
        { name: "GitHub", href: "https://github.com", icon: Code2 },
        { name: "Twitter", href: "https://twitter.com", icon: Share2 },
        { name: "LinkedIn", href: "https://linkedin.com", icon: Globe },
        { name: "Discord", href: "https://discord.com", icon: MessageCircle },
    ];

    return (
        <div className="flex items-center gap-3">
            {socials.map((s, idx) => {
                const Icon = s.icon;
                return (
                    <Link
                        key={idx}
                        href={s.href}
                        target="_blank"
                        rel="noreferrer"
                        className="flex h-9 w-9 items-center justify-center rounded-xl border border-border bg-background text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                    >
                        <Icon className="h-4 w-4" />
                        <span className="sr-only">{s.name}</span>
                    </Link>
                );
            })}
        </div>
    );
}
