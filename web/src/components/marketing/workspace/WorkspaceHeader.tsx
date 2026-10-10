"use client";

import {
    Bell,
    Search,
    Settings,
} from "lucide-react";

import ExecutionModeBadge from "@/components/chat/ExecutionModeBadge";

export default function WorkspaceHeader() {
    return (
        <header className="flex items-center justify-between border-b border-border bg-background/80 px-6 py-4 backdrop-blur-xl">

            <div>

                <h3 className="text-lg font-semibold">
                    Enterprise AI Workspace
                </h3>

                <p className="text-xs text-muted-foreground">
                    AMOF Session • Connected
                </p>

            </div>

            <div className="flex items-center gap-3">

                <ExecutionModeBadge mode="local" />

                <Search
                    size={18}
                    className="text-muted-foreground"
                />

                <Bell
                    size={18}
                    className="text-muted-foreground"
                />

                <Settings
                    size={18}
                    className="text-muted-foreground"
                />

            </div>

        </header>
    );
}