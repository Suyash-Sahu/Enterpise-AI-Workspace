import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Props {
    children: ReactNode;
    className?: string;
    id?: string;
    /** Tighter vertical rhythm (py-16 instead of py-24). */
    tight?: boolean;
    /** Paint the section on the raised surface instead of the page ground. */
    surface?: boolean;
}

export default function Section({
    children,
    className,
    id,
    tight = false,
    surface = false,
}: Props) {
    return (
        <section
            id={id}
            className={cn(
                tight ? "py-16" : "py-24",
                surface && "bg-surface",
                className
            )}
        >
            {children}
        </section>
    );
}
