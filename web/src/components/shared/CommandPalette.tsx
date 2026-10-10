"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
    ArrowRight,
    BarChart3,
    Bot,
    Cpu,
    Database,
    FileText,
    HardDrive,
    LayoutDashboard,
    Mail,
    MessageSquare,
    Search,
    Settings,
    ShieldCheck,
    Sparkles,
    SquareKanban,
    Video,
    type LucideIcon,
} from "lucide-react";

import { ROUTES } from "@/constants/routes";
import { SEED_PROJECTS, SEED_DOCUMENTS } from "@/data/central-store";
import { cn } from "@/lib/utils";

interface Action {
    id: string;
    label: string;
    hint?: string;
    icon: LucideIcon;
    run: () => void;
}

const NAV: { label: string; path: string; icon: LucideIcon }[] = [
    { label: "Dashboard", path: ROUTES.DASHBOARD, icon: LayoutDashboard },
    { label: "Workspace Chat", path: ROUTES.CHAT, icon: MessageSquare },
    { label: "AI Writer", path: ROUTES.WRITER, icon: Sparkles },
    { label: "AI Documents", path: ROUTES.DOCUMENTS, icon: FileText },
    { label: "Google Drive", path: ROUTES.DRIVE, icon: HardDrive },
    { label: "Gmail", path: ROUTES.GMAIL, icon: Mail },
    { label: "Google Meet", path: ROUTES.MEET, icon: Video },
    { label: "Database Agent", path: "/database", icon: Database },
    { label: "AI Execution", path: "/execution", icon: Cpu },
    { label: "AMOF Supervisor", path: "/supervisor", icon: Bot },
    { label: "Research & Eval", path: ROUTES.RESEARCH, icon: BarChart3 },
    { label: "Integrations", path: ROUTES.INTEGRATIONS, icon: Settings },
    { label: "Settings", path: ROUTES.SETTINGS, icon: Settings },
    // Admin-only server-side (require_role); listed for discoverability --
    // a non-admin who opens it gets the API's 403 rendered as such.
    { label: "Admin Telemetry", path: ROUTES.ADMIN, icon: ShieldCheck },
];

export default function CommandPalette() {
    const router = useRouter();
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const [active, setActive] = useState(0);

    const close = () => {
        setOpen(false);
        setQuery("");
        setActive(0);
    };

    useEffect(() => {
        // Toggling always starts from a clean slate; clearing on the way out
        // too is harmless and avoids a reset effect.
        const toggle = () => {
            setQuery("");
            setActive(0);
            setOpen((v) => !v);
        };
        const onKey = (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                toggle();
            }
        };
        window.addEventListener("commandpalette:toggle", toggle);
        window.addEventListener("keydown", onKey);
        return () => {
            window.removeEventListener("commandpalette:toggle", toggle);
            window.removeEventListener("keydown", onKey);
        };
    }, []);

    const go = (path: string) => {
        close();
        router.push(path);
    };

    const actions = useMemo<Action[]>(() => {
        const q = query.trim().toLowerCase();
        const list: Action[] = [];

        if (q) {
            list.push({
                id: "ask-ai",
                label: `Ask the AI assistant: “${query.trim()}”`,
                icon: Sparkles,
                run: () => go(`${ROUTES.CHAT}?prompt=${encodeURIComponent(query.trim())}`),
            });
        }

        NAV.filter((n) => n.label.toLowerCase().includes(q)).forEach((n) =>
            list.push({
                id: `nav-${n.path}`,
                label: n.label,
                hint: "Page",
                icon: n.icon,
                run: () => go(n.path),
            })
        );

        SEED_PROJECTS.filter((p) => p.name.toLowerCase().includes(q))
            .slice(0, 5)
            .forEach((p) =>
                list.push({
                    id: `project-${p.id}`,
                    label: p.name,
                    hint: "Project",
                    icon: SquareKanban,
                    run: () => go(`${ROUTES.PROJECTS}?id=${p.id}`),
                })
            );

        SEED_DOCUMENTS.filter((d) => d.name.toLowerCase().includes(q))
            .slice(0, 5)
            .forEach((d) =>
                list.push({
                    id: `doc-${d.id}`,
                    label: d.name,
                    hint: "Document",
                    icon: FileText,
                    run: () => go(`${ROUTES.DOCUMENTS}?id=${d.id}`),
                })
            );

        return list;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [query]);

    if (!open) return null;

    // `active` is reset to 0 on every query change, so it can only ever hold a
    // valid index; this guard is just defensive for the empty-result frame.
    const current = actions.length ? Math.min(active, actions.length - 1) : 0;

    const onKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Escape") {
            close();
        } else if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => (a + 1) % Math.max(1, actions.length));
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => (a - 1 + actions.length) % Math.max(1, actions.length));
        } else if (e.key === "Enter") {
            e.preventDefault();
            actions[current]?.run();
        }
    };

    return (
        <div
            className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 pt-[10vh] backdrop-blur-sm animate-in fade-in"
            onClick={close}
        >
            <div
                role="dialog"
                aria-modal="true"
                aria-label="Command palette"
                className="w-full max-w-xl overflow-hidden rounded-md border border-border bg-popover text-popover-foreground shadow-md animate-in fade-in zoom-in-95"
                onClick={(e) => e.stopPropagation()}
                onKeyDown={onKeyDown}
            >
                <div className="flex items-center gap-3 border-b border-border px-4">
                    <Search className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                    <input
                        autoFocus
                        type="text"
                        role="combobox"
                        aria-expanded="true"
                        aria-controls="cmdk-list"
                        aria-activedescendant={
                            actions.length ? `cmdk-opt-${current}` : undefined
                        }
                        aria-label="Search or run a command"
                        placeholder="Search pages, projects, documents…"
                        value={query}
                        onChange={(e) => {
                            setQuery(e.target.value);
                            setActive(0);
                        }}
                        className="h-12 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
                    />
                    <kbd className="hidden shrink-0 rounded-sm border border-border px-1.5 text-xs font-medium text-muted-foreground sm:block">
                        Esc
                    </kbd>
                </div>

                <div
                    id="cmdk-list"
                    role="listbox"
                    aria-label="Results"
                    className="max-h-80 overflow-y-auto p-1.5"
                >
                    {actions.length === 0 ? (
                        <p className="px-3 py-6 text-center text-sm text-muted-foreground">
                            No matches.
                        </p>
                    ) : (
                        actions.map((a, i) => {
                            const Icon = a.icon;
                            return (
                                <button
                                    key={a.id}
                                    type="button"
                                    role="option"
                                    id={`cmdk-opt-${i}`}
                                    tabIndex={-1}
                                    onMouseMove={() => setActive(i)}
                                    onClick={a.run}
                                    aria-selected={i === current}
                                    className={cn(
                                        "flex w-full items-center gap-3 rounded-sm px-3 py-2 text-left text-sm transition-colors",
                                        i === current
                                            ? "bg-accent text-foreground"
                                            : "text-muted-foreground"
                                    )}
                                >
                                    <Icon className="h-4 w-4 shrink-0" aria-hidden />
                                    <span className="flex-1 truncate text-foreground">
                                        {a.label}
                                    </span>
                                    {a.hint && (
                                        <span className="shrink-0 text-xs text-muted-foreground">
                                            {a.hint}
                                        </span>
                                    )}
                                    <ArrowRight
                                        className={cn(
                                            "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-opacity",
                                            i === active ? "opacity-100" : "opacity-0"
                                        )}
                                        aria-hidden
                                    />
                                </button>
                            );
                        })
                    )}
                </div>
            </div>
        </div>
    );
}
