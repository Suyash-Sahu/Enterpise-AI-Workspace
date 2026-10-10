"use client";

import { useState } from "react";
import { useTheme } from "next-themes";
import {
    AlertTriangle,
    Bell,
    Building2,
    HardDrive,
    Lock,
    Monitor,
    Moon,
    Palette,
    Puzzle,
    Shield,
    Sparkles,
    Sun,
    User,
    Users,
} from "lucide-react";

import PageHeader from "@/components/shared/PageHeader";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useSettingsStore } from "@/stores/settings.store";
import { useWorkspaceStore } from "@/stores/workspace.store";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

type TabId =
    | "profile"
    | "workspace"
    | "appearance"
    | "security"
    | "notifications"
    | "ai"
    | "members"
    | "apps"
    | "privacy"
    | "storage";

const TABS: { id: TabId; label: string; icon: typeof User }[] = [
    { id: "profile", label: "Profile", icon: User },
    { id: "workspace", label: "Workspace", icon: Building2 },
    { id: "appearance", label: "Appearance", icon: Palette },
    { id: "security", label: "Security & 2FA", icon: Shield },
    { id: "notifications", label: "Notifications", icon: Bell },
    { id: "ai", label: "AI preferences", icon: Sparkles },
    { id: "members", label: "Members", icon: Users },
    { id: "apps", label: "Connected apps", icon: Puzzle },
    { id: "privacy", label: "Privacy", icon: Lock },
    { id: "storage", label: "Storage", icon: HardDrive },
];

const THEMES: { id: string; label: string; icon: typeof Moon }[] = [
    { id: "light", label: "Light", icon: Sun },
    { id: "dark", label: "Dark", icon: Moon },
    { id: "system", label: "System", icon: Monitor },
];

export default function SettingsPage() {
    const { executionMode, setExecutionMode } = useSettingsStore();
    const { currentWorkspace, members } = useWorkspaceStore();
    const { user } = useAuth();
    const { theme, setTheme } = useTheme();

    const [activeTab, setActiveTab] = useState<TabId>("profile");
    const [isDeleteOpen, setIsDeleteOpen] = useState(false);

    const [fullName, setFullName] = useState(user?.fullName ?? "");
    const [email, setEmail] = useState(user?.email ?? "");
    const [workspaceName, setWorkspaceName] = useState(currentWorkspace.name);
    const [mfaEnabled, setMfaEnabled] = useState(true);

    return (
        <div className="space-y-6">
            <PageHeader
                title="Settings"
                description="Profile, workspace, appearance, security, and AI preferences."
                breadcrumbs={[{ label: "Workspace" }, { label: "Settings" }]}
            />

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
                <nav className="space-y-1" aria-label="Settings sections">
                    {TABS.map(({ id, label, icon: Icon }) => {
                        const selected = activeTab === id;
                        return (
                            <button
                                key={id}
                                type="button"
                                onClick={() => setActiveTab(id)}
                                aria-current={selected ? "page" : undefined}
                                className={cn(
                                    "flex w-full items-center gap-3 rounded-sm px-3 py-2 text-sm transition-colors",
                                    selected
                                        ? "bg-accent font-medium text-foreground"
                                        : "text-muted-foreground hover:bg-accent hover:text-foreground"
                                )}
                            >
                                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                                {label}
                            </button>
                        );
                    })}
                </nav>

                <div className="space-y-6 lg:col-span-3">
                    {activeTab === "profile" && (
                        <Card className="p-6">
                            <h2 className="border-b border-border pb-3 text-sm font-semibold text-foreground">
                                Profile
                            </h2>
                            <div className="mt-4 flex items-center gap-4">
                                <span className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-lg font-semibold text-primary">
                                    {(fullName || "U").charAt(0).toUpperCase()}
                                </span>
                                <div>
                                    <p className="text-sm font-medium text-foreground">
                                        {fullName || "Your name"}
                                    </p>
                                    <p className="text-sm text-muted-foreground">{email}</p>
                                    <Badge variant="secondary" className="mt-1">
                                        {user?.role ?? "Member"}
                                    </Badge>
                                </div>
                            </div>
                            <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
                                <Field label="Full name">
                                    <Input
                                        value={fullName}
                                        onChange={(e) => setFullName(e.target.value)}
                                    />
                                </Field>
                                <Field label="Email address">
                                    <Input
                                        type="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                    />
                                </Field>
                            </div>
                            <div className="mt-6">
                                <Button size="sm">Save changes</Button>
                            </div>
                        </Card>
                    )}

                    {activeTab === "workspace" && (
                        <Card className="p-6">
                            <h2 className="border-b border-border pb-3 text-sm font-semibold text-foreground">
                                Workspace
                            </h2>
                            <div className="mt-4 max-w-md">
                                <Field label="Workspace name">
                                    <Input
                                        value={workspaceName}
                                        onChange={(e) => setWorkspaceName(e.target.value)}
                                    />
                                </Field>
                            </div>
                        </Card>
                    )}

                    {activeTab === "appearance" && (
                        <Card className="p-6">
                            <h2 className="border-b border-border pb-3 text-sm font-semibold text-foreground">
                                Appearance
                            </h2>
                            <p className="mt-4 text-sm font-medium text-foreground">Theme</p>
                            <div className="mt-2 grid max-w-md grid-cols-3 gap-3">
                                {THEMES.map(({ id, label, icon: Icon }) => {
                                    const selected = theme === id;
                                    return (
                                        <button
                                            key={id}
                                            type="button"
                                            onClick={() => setTheme(id)}
                                            aria-pressed={selected}
                                            className={cn(
                                                "flex flex-col items-center gap-2 rounded-sm border p-4 text-sm transition-colors",
                                                selected
                                                    ? "border-primary bg-primary/10 text-primary"
                                                    : "border-border text-muted-foreground hover:bg-accent hover:text-foreground"
                                            )}
                                        >
                                            <Icon className="h-5 w-5" aria-hidden />
                                            {label}
                                        </button>
                                    );
                                })}
                            </div>
                        </Card>
                    )}

                    {activeTab === "security" && (
                        <Card className="p-6">
                            <h2 className="border-b border-border pb-3 text-sm font-semibold text-foreground">
                                Security &amp; two-factor authentication
                            </h2>
                            <label className="mt-4 flex items-center justify-between gap-4 rounded-sm border border-border bg-muted/40 p-3">
                                <span>
                                    <span className="block text-sm font-medium text-foreground">
                                        Two-factor authentication
                                    </span>
                                    <span className="block text-xs text-muted-foreground">
                                        Require a 6-digit code at sign-in.
                                    </span>
                                </span>
                                <input
                                    type="checkbox"
                                    checked={mfaEnabled}
                                    onChange={(e) => setMfaEnabled(e.target.checked)}
                                    className="h-4 w-4 accent-primary"
                                />
                            </label>
                        </Card>
                    )}

                    {activeTab === "ai" && (
                        <Card className="p-6">
                            <h2 className="border-b border-border pb-3 text-sm font-semibold text-foreground">
                                AI preferences
                            </h2>
                            <p className="mt-4 text-sm font-medium text-foreground">
                                Execution router
                            </p>
                            <div className="mt-2 grid max-w-md grid-cols-3 gap-3">
                                {(["Hybrid", "Local", "Cloud"] as const).map((m) => {
                                    const selected = executionMode === m;
                                    return (
                                        <button
                                            key={m}
                                            type="button"
                                            onClick={() => setExecutionMode(m)}
                                            aria-pressed={selected}
                                            className={cn(
                                                "rounded-sm border p-3 text-sm transition-colors",
                                                selected
                                                    ? "border-primary bg-primary/10 text-primary"
                                                    : "border-border text-muted-foreground hover:bg-accent hover:text-foreground"
                                            )}
                                        >
                                            {m}
                                        </button>
                                    );
                                })}
                            </div>
                        </Card>
                    )}

                    {activeTab === "members" && (
                        <Card className="p-6">
                            <h2 className="border-b border-border pb-3 text-sm font-semibold text-foreground">
                                Members ({members.length})
                            </h2>
                            <div className="mt-4 space-y-2">
                                {members.map((m) => (
                                    <div
                                        key={m.id}
                                        className="flex items-center justify-between gap-3 rounded-sm border border-border bg-muted/40 p-3"
                                    >
                                        <div className="flex min-w-0 items-center gap-3">
                                            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                                                {m.name.charAt(0)}
                                            </span>
                                            <div className="min-w-0">
                                                <p className="truncate text-sm font-medium text-foreground">
                                                    {m.name}
                                                </p>
                                                <p className="truncate text-xs text-muted-foreground">
                                                    {m.email}
                                                </p>
                                            </div>
                                        </div>
                                        <Badge variant="secondary">{m.role}</Badge>
                                    </div>
                                ))}
                            </div>
                        </Card>
                    )}

                    {activeTab === "storage" && (
                        <Card className="p-6">
                            <h2 className="border-b border-border pb-3 text-sm font-semibold text-foreground">
                                Storage
                            </h2>
                            <div className="mt-4 space-y-2">
                                <div className="flex justify-between text-sm text-muted-foreground">
                                    <span>5.2 GB used</span>
                                    <span>10 GB quota</span>
                                </div>
                                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                                    <div className="h-full w-1/2 rounded-full bg-primary" />
                                </div>
                            </div>
                        </Card>
                    )}

                    {(activeTab === "notifications" ||
                        activeTab === "apps" ||
                        activeTab === "privacy") && (
                        <Card className="p-6 text-sm text-muted-foreground">
                            This section is not configured yet.
                        </Card>
                    )}

                    <Card className="border-destructive/30 bg-destructive/5 p-6">
                        <div className="flex items-center gap-2 text-sm font-semibold text-destructive">
                            <AlertTriangle className="h-4 w-4" aria-hidden />
                            Danger zone
                        </div>
                        <p className="mt-2 text-sm text-muted-foreground">
                            Deleting a workspace is permanent and removes all its data.
                        </p>
                        <Button
                            variant="destructive"
                            size="sm"
                            className="mt-3"
                            onClick={() => setIsDeleteOpen(true)}
                        >
                            Delete workspace
                        </Button>
                    </Card>
                </div>
            </div>

            <ConfirmDialog
                isOpen={isDeleteOpen}
                title="Delete workspace"
                description="Delete this workspace? All projects, tasks, documents, and notifications will be permanently removed."
                confirmText="Delete workspace"
                onConfirm={() => setIsDeleteOpen(false)}
                onClose={() => setIsDeleteOpen(false)}
            />
        </div>
    );
}

function Field({
    label,
    children,
}: {
    label: string;
    children: React.ReactNode;
}) {
    return (
        <label className="block space-y-1.5">
            <span className="block text-xs font-medium text-foreground">{label}</span>
            {children}
        </label>
    );
}
