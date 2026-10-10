"use client";

interface Props {
    activeCategory: string;
    onSelect: (category: string) => void;
}

const CATEGORIES = [
    { id: "all", label: "All Capabilities" },
    { id: "agents", label: "Multi-Agent Engine" },
    { id: "execution", label: "Local & Cloud Execution" },
    { id: "search", label: "RAG & Text-to-SQL" },
    { id: "security", label: "Security & Governance" },
];

export default function FeatureTabs({ activeCategory, onSelect }: Props) {
    return (
        <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
            {CATEGORIES.map((tab) => {
                const isActive = activeCategory === tab.id;
                return (
                    <button
                        key={tab.id}
                        onClick={() => onSelect(tab.id)}
                        className={`rounded-full px-4 py-2 text-xs font-semibold transition-all duration-200 ${
                            isActive
                                ? "bg-primary text-primary-foreground shadow-md"
                                : "border border-border bg-background/60 text-muted-foreground hover:border-primary/40 hover:text-foreground"
                        }`}
                    >
                        {tab.label}
                    </button>
                );
            })}
        </div>
    );
}
