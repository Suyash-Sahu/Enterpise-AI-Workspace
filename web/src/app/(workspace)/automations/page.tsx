"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Loader2, Play, Sparkles, Zap, AlertTriangle } from "lucide-react";

import PageHeader from "@/components/shared/PageHeader";
import DataState from "@/components/shared/DataState";
import EmptyState from "@/components/shared/EmptyState";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    useAutomations,
    useCreateAutomation,
    useDraftAutomationFromText,
    useRunAutomationNow,
    useUpdateAutomation,
} from "@/hooks/useAutomations";
import { AutomationDraftDTO, AutomationDTO } from "@/types/automation";

export default function AutomationsPage() {
    const [text, setText] = useState("");
    const [draft, setDraft] = useState<AutomationDraftDTO | null>(null);
    const draftMutation = useDraftAutomationFromText();
    const createMutation = useCreateAutomation();
    const { data: automations, isLoading, isError, error, refetch } = useAutomations();

    const handleDraft = (e: React.FormEvent) => {
        e.preventDefault();
        if (!text.trim()) return;
        draftMutation.mutate(text, {
            onSuccess: (result) => setDraft(result),
            onError: () => toast.error("Could not interpret that request"),
        });
    };

    const handleConfirm = () => {
        if (!draft?.draft) return;
        createMutation.mutate(
            { ...draft.draft, enabled: true },
            {
                onSuccess: () => {
                    toast.success("Automation created");
                    setDraft(null);
                    setText("");
                },
                onError: () => toast.error("Could not create automation"),
            }
        );
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Automations"
                description="Describe a recurring automation in plain English, or manage the ones you already have."
            />

            <form onSubmit={handleDraft} className="space-y-3 rounded-2xl border border-border bg-surface p-5 shadow-sm">
                <label className="block text-xs font-bold text-foreground">
                    e.g. &quot;Every weekday at 9 AM, check my important emails and overdue tasks and give me a summary.&quot;
                </label>
                <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    rows={3}
                    placeholder="Describe the automation..."
                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                />
                <div className="flex justify-end">
                    <Button type="submit" size="sm" disabled={draftMutation.isPending}>
                        {draftMutation.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}
                        Draft automation
                    </Button>
                </div>
            </form>

            {draft && (
                <Card className="p-5">
                    {draft.needs_clarification ? (
                        <div className="flex items-start gap-2 text-sm text-warning">
                            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                            <span>{draft.clarification}</span>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <h3 className="text-sm font-semibold text-foreground">{draft.draft?.name}</h3>
                                <Badge variant="secondary">{draft.draft?.trigger_type}</Badge>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                {draft.draft?.trigger_type === "schedule"
                                    ? `Schedule: ${draft.draft?.schedule}`
                                    : `Condition: ${JSON.stringify(draft.draft?.condition)}`}
                            </p>
                            <ul className="space-y-1 text-xs text-muted-foreground">
                                {draft.draft?.steps.map((s) => (
                                    <li key={s.step_id}>&bull; {s.capability}</li>
                                ))}
                            </ul>
                            {draft.warnings.length > 0 && (
                                <div className="space-y-1 rounded-md border border-warning/30 bg-warning/10 p-2 text-xs text-warning">
                                    {draft.warnings.map((w, i) => (
                                        <p key={i}>{w}</p>
                                    ))}
                                </div>
                            )}
                            <div className="flex justify-end gap-2">
                                <Button variant="outline" size="sm" onClick={() => setDraft(null)}>
                                    Discard
                                </Button>
                                <Button size="sm" disabled={createMutation.isPending} onClick={handleConfirm}>
                                    Confirm & create
                                </Button>
                            </div>
                        </div>
                    )}
                </Card>
            )}

            <div>
                <h3 className="mb-3 text-sm font-semibold text-foreground">Your automations</h3>
                <DataState
                    isLoading={isLoading}
                    isError={isError}
                    error={error}
                    isEmpty={!automations?.length}
                    onRetry={() => refetch()}
                    resource="automations"
                    skeletonVariant="list"
                    empty={
                        <EmptyState
                            icon={<Zap />}
                            title="No automations yet"
                            description="Draft one above, or enable the Daily Digest from the Morning Brief page."
                        />
                    }
                >
                    <div className="space-y-2">
                        {(automations ?? []).map((a) => (
                            <AutomationRow key={a.id} automation={a} />
                        ))}
                    </div>
                </DataState>
            </div>
        </div>
    );
}

function AutomationRow({ automation }: { automation: AutomationDTO }) {
    const updateMutation = useUpdateAutomation();
    const runMutation = useRunAutomationNow();

    return (
        <Card className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
                <p className="truncate text-sm font-medium text-foreground">{automation.name}</p>
                <p className="text-xs text-muted-foreground">
                    {automation.trigger_type === "schedule" ? automation.schedule : automation.trigger_type}
                    {" · "}
                    {automation.steps.map((s) => s.capability).join(", ")}
                </p>
            </div>
            <div className="flex items-center gap-2">
                <Badge variant={automation.enabled ? "success" : "secondary"}>
                    {automation.enabled ? "Enabled" : "Disabled"}
                </Badge>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                        updateMutation.mutate(
                            { id: automation.id, data: { enabled: !automation.enabled } },
                            { onError: () => toast.error("Could not update automation") }
                        )
                    }
                >
                    {automation.enabled ? "Disable" : "Enable"}
                </Button>
                <Button
                    size="sm"
                    disabled={!automation.enabled || runMutation.isPending}
                    onClick={() =>
                        runMutation.mutate(automation.id, {
                            onSuccess: () => toast.success("Automation run started"),
                            onError: () => toast.error("Could not run automation"),
                        })
                    }
                >
                    <Play aria-hidden />
                    Run now
                </Button>
            </div>
        </Card>
    );
}
