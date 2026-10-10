export default function TypingIndicator() {
    return (
        <div className="flex w-fit items-center gap-2 rounded-md border border-border bg-background px-4 py-3">
            <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-primary/70" />
                <span className="h-1.5 w-1.5 rounded-full bg-primary/50" />
                <span className="h-1.5 w-1.5 rounded-full bg-primary/30" />
            </span>
            <span className="ml-1 text-xs text-muted-foreground">
                Generating a response…
            </span>
        </div>
    );
}
