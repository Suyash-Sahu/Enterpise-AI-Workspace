"use client";

import React from "react";
import SearchInput from "@/components/shared/SearchInput";
import { Button } from "@/components/ui/button";
import {
    Table,
    Send,
    BarChart3,
    History,
    Filter,
} from "lucide-react";

interface CommitmentFiltersProps {
    search: string;
    onSearchChange: (val: string) => void;
    direction: string;
    onDirectionChange: (val: string) => void;
    status: string;
    onStatusChange: (val: string) => void;
    sourceType: string;
    onSourceTypeChange: (val: string) => void;
    priority: string;
    onPriorityChange: (val: string) => void;
    viewMode: "table" | "followup" | "analytics" | "history";
    onViewModeChange: (val: "table" | "followup" | "analytics" | "history") => void;
}

const DIRECTION_OPTIONS = [
    { key: "all", label: "All Directions" },
    { key: "owed_by_me", label: "Owed by Me" },
    { key: "owed_to_me", label: "Owed to Me" },
    { key: "mutual", label: "Mutual" },
];

const STATUS_OPTIONS = [
    { key: "all", label: "All Statuses" },
    { key: "pending", label: "Pending" },
    { key: "at_risk", label: "At Risk" },
    { key: "overdue", label: "Overdue" },
    { key: "completed", label: "Completed" },
    { key: "dismissed", label: "Dismissed" },
];

export function CommitmentFilters({
    search,
    onSearchChange,
    direction,
    onDirectionChange,
    status,
    onStatusChange,
    sourceType,
    onSourceTypeChange,
    priority,
    onPriorityChange,
    viewMode,
    onViewModeChange,
}: CommitmentFiltersProps) {
    return (
        <div className="space-y-3">
            {/* Top Toolbar: View switcher + Search */}
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                {/* View Mode Pills */}
                <div className="inline-flex rounded-lg border border-border bg-muted/40 p-1 text-xs">
                    <button
                        onClick={() => onViewModeChange("table")}
                        className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition-all ${
                            viewMode === "table"
                                ? "bg-background text-foreground shadow-sm"
                                : "text-muted-foreground hover:text-foreground"
                        }`}
                    >
                        <Table className="h-3.5 w-3.5" />
                        Workspace
                    </button>
                    <button
                        onClick={() => onViewModeChange("followup")}
                        className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition-all ${
                            viewMode === "followup"
                                ? "bg-background text-foreground shadow-sm"
                                : "text-muted-foreground hover:text-foreground"
                        }`}
                    >
                        <Send className="h-3.5 w-3.5" />
                        Follow-Up Center
                    </button>
                    <button
                        onClick={() => onViewModeChange("analytics")}
                        className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition-all ${
                            viewMode === "analytics"
                                ? "bg-background text-foreground shadow-sm"
                                : "text-muted-foreground hover:text-foreground"
                        }`}
                    >
                        <BarChart3 className="h-3.5 w-3.5" />
                        Analytics
                    </button>
                    <button
                        onClick={() => onViewModeChange("history")}
                        className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition-all ${
                            viewMode === "history"
                                ? "bg-background text-foreground shadow-sm"
                                : "text-muted-foreground hover:text-foreground"
                        }`}
                    >
                        <History className="h-3.5 w-3.5" />
                        Execution History
                    </button>
                </div>

                {/* Search Box */}
                <div className="w-full sm:w-72">
                    <SearchInput
                        value={search}
                        onChange={onSearchChange}
                        placeholder="Search commitments, owners..."
                        className="h-9 text-xs"
                    />
                </div>
            </div>

            {/* Filter Pills row: Direction + Status + Source + Priority */}
            {viewMode === "table" && (
                <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-border/50">
                    {/* Direction Filter */}
                    <div className="flex items-center gap-1">
                        {DIRECTION_OPTIONS.map((opt) => (
                            <button
                                key={opt.key}
                                onClick={() => onDirectionChange(opt.key)}
                                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                                    direction === opt.key
                                        ? "bg-primary text-primary-foreground"
                                        : "bg-muted/50 text-muted-foreground hover:bg-muted"
                                }`}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>

                    <div className="h-4 w-[1px] bg-border mx-1 hidden sm:block" />

                    {/* Status Filter */}
                    <div className="flex items-center gap-1">
                        {STATUS_OPTIONS.map((opt) => (
                            <button
                                key={opt.key}
                                onClick={() => onStatusChange(opt.key)}
                                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                                    status === opt.key
                                        ? "bg-secondary text-secondary-foreground font-semibold"
                                        : "text-muted-foreground hover:bg-muted"
                                }`}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>

                    {/* Source Selector */}
                    <div className="ml-auto flex items-center gap-2">
                        <select
                            value={sourceType}
                            onChange={(e) => onSourceTypeChange(e.target.value)}
                            className="h-7 rounded-md border border-border bg-background px-2 text-xs text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                        >
                            <option value="all">All Sources</option>
                            <option value="gmail">Gmail</option>
                            <option value="meeting">Meetings</option>
                            <option value="manual">Manual</option>
                        </select>

                        <select
                            value={priority}
                            onChange={(e) => onPriorityChange(e.target.value)}
                            className="h-7 rounded-md border border-border bg-background px-2 text-xs text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                        >
                            <option value="all">All Priorities</option>
                            <option value="high">High</option>
                            <option value="medium">Medium</option>
                            <option value="low">Low</option>
                        </select>
                    </div>
                </div>
            )}
        </div>
    );
}

