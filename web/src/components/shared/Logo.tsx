import { BrainCircuit } from "lucide-react";

import { cn } from "@/lib/utils";

interface Props {
    /** Hide the wordmark, show only the glyph (collapsed sidebar). */
    iconOnly?: boolean;
    className?: string;
}

/**
 * The one brand mark, used in both the marketing nav and the app shell.
 */
export default function Logo({ iconOnly = false, className }: Props) {
    return (
        <span className={cn("flex items-center gap-2.5", className)}>
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <BrainCircuit className="h-5 w-5" aria-hidden />
            </span>
            {!iconOnly && (
                <span className="flex flex-col leading-none">
                    <span className="text-sm font-semibold tracking-tight text-foreground">
                        Enterprise AI
                    </span>
                    <span className="mt-0.5 text-xs font-medium text-muted-foreground">
                        Workspace
                    </span>
                </span>
            )}
        </span>
    );
}
