interface Props {
    variant?: "card" | "list" | "table";
    count?: number;
}

export default function LoadingSkeleton({ variant = "card", count = 3 }: Props) {
    const items = Array.from({ length: count });

    if (variant === "list") {
        return (
            <div className="space-y-3" role="status" aria-label="Loading">
                {items.map((_, i) => (
                    <div
                        key={i}
                        className="h-16 w-full animate-pulse rounded-md border border-border bg-muted"
                    />
                ))}
            </div>
        );
    }

    if (variant === "table") {
        return (
            <div className="space-y-2" role="status" aria-label="Loading">
                <div className="h-10 w-full animate-pulse rounded-sm bg-muted" />
                {items.map((_, i) => (
                    <div
                        key={i}
                        className="h-12 w-full animate-pulse rounded-sm bg-muted/60"
                    />
                ))}
            </div>
        );
    }

    return (
        <div
            className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
            role="status"
            aria-label="Loading"
        >
            {items.map((_, i) => (
                <div
                    key={i}
                    className="h-40 w-full animate-pulse space-y-3 rounded-md border border-border bg-card p-6"
                >
                    <div className="h-4 w-1/3 rounded-sm bg-muted" />
                    <div className="h-3 w-3/4 rounded-sm bg-muted/70" />
                    <div className="h-12 w-full rounded-sm bg-muted/50" />
                </div>
            ))}
        </div>
    );
}
