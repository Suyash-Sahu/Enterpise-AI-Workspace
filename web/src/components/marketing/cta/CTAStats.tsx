export default function CTAStats() {
    const stats = [
        { label: "Active Enterprise Agents", value: "8 Agents" },
        { label: "Connectors Integrated", value: "30+ SaaS & DBs" },
        { label: "Local Privacy Rating", value: "100% On-Device" },
        { label: "Average Setup Time", value: "< 5 Minutes" },
    ];

    return (
        <div className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto">
            {stats.map((s, idx) => (
                <div key={idx} className="rounded-xl border border-border bg-background/60 p-4 text-center">
                    <div className="text-xl font-semibold text-primary">{s.value}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{s.label}</div>
                </div>
            ))}
        </div>
    );
}
