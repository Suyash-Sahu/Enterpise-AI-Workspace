"use client";

interface Props {
    activeCategory: string;
    onSelect: (category: string) => void;
}

const CATEGORIES = [
    { id: "all", label: "All Integrations" },
    { id: "google", label: "Google Workspace" },
    { id: "microsoft", label: "Microsoft 365" },
    { id: "productivity", label: "Slack & Notion" },
    { id: "developer", label: "Jira & Linear" },
    { id: "database", label: "Databases & Local Files" },
];

export default function IntegrationCategory({ activeCategory, onSelect }: Props) {
    return (
        <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
            {CATEGORIES.map((cat) => {
                const isActive = activeCategory === cat.id;
                return (
                    <button
                        key={cat.id}
                        onClick={() => onSelect(cat.id)}
                        className={`rounded-full px-4 py-1.5 text-xs font-medium transition-all duration-200 ${
                            isActive
                                ? "bg-primary text-primary-foreground shadow-md"
                                : "border border-border bg-background/60 text-muted-foreground hover:border-primary/40 hover:text-foreground"
                        }`}
                    >
                        {cat.label}
                    </button>
                );
            })}
        </div>
    );
}
