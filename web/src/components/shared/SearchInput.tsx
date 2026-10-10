"use client";

import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
    value: string;
    onChange: (val: string) => void;
    placeholder?: string;
    className?: string;
    "aria-label"?: string;
}

export default function SearchInput({
    value,
    onChange,
    placeholder = "Search...",
    className,
    "aria-label": ariaLabel,
}: Props) {
    return (
        <div className={cn("relative flex w-full items-center", className)}>
            <Search
                className="pointer-events-none absolute left-3 h-4 w-4 text-muted-foreground"
                aria-hidden
            />
            <input
                type="search"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                aria-label={ariaLabel ?? placeholder}
                className="h-9 w-full rounded-sm border border-input bg-surface pl-9 pr-8 text-sm text-foreground shadow-2xs transition-[color,box-shadow] outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
            />
            {value && (
                <button
                    type="button"
                    onClick={() => onChange("")}
                    aria-label="Clear search"
                    className="absolute right-2 rounded-full p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                    <X className="h-3.5 w-3.5" aria-hidden />
                </button>
            )}
        </div>
    );
}
