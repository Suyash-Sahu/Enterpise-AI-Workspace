import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface ContainerProps {
    children: ReactNode;
    className?: string;
    /** default = marketing width (max-w-7xl); wide = app content (1400px); prose = reading width. */
    size?: "default" | "wide" | "prose";
}

const widths = {
    default: "max-w-7xl",
    wide: "max-w-[1400px]",
    prose: "max-w-3xl",
};

export default function Container({
    children,
    className,
    size = "default",
}: ContainerProps) {
    return (
        <div
            className={cn(
                "mx-auto w-full px-6 lg:px-8",
                widths[size],
                className
            )}
        >
            {children}
        </div>
    );
}
