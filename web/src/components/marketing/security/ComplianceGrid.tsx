import { Shield, Lock, FileCheck, Server, Key, Eye } from "lucide-react";

export default function ComplianceGrid() {
    const Badges = [
        { label: "Zero-Trust Architecture", desc: "No permanent credential storage", icon: Shield },
        { label: "AES-256 Key Encryption", desc: "Local OS keychain isolation", icon: Lock },
        { label: "Immutable Audit Trails", desc: "Every action logged with hash signature", icon: FileCheck },
        { label: "SOC2 Ready Patterns", desc: "Enterprise RBAC & SSO integration", icon: Server },
    ];

    return (
        <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {Badges.map((b, idx) => {
                const Icon = b.icon;
                return (
                    <div key={idx} className="flex items-center gap-3 rounded-xl border border-border bg-background/60 p-4">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                            <Icon className="h-5 w-5" />
                        </div>
                        <div>
                            <div className="text-xs font-bold text-foreground">{b.label}</div>
                            <div className="text-xs text-muted-foreground">{b.desc}</div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
