"use client";

import { useCallback, useEffect, useState } from "react";

import { WorkService } from "@/services/work.service";
import type { CommentDTO } from "@/types/project";

/** Comment text is untrusted data: it is only ever rendered as escaped React text, never as HTML. */
export function ItemComments({ taskId }: { taskId: string }) {
    const [comments, setComments] = useState<CommentDTO[]>([]);
    const [draft, setDraft] = useState("");
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editText, setEditText] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [tick, setTick] = useState(0);
    const load = useCallback(() => setTick((t) => t + 1), []);

    useEffect(() => {
        let cancelled = false;
        WorkService.getComments(taskId)
            .then((list) => {
                if (!cancelled) setComments(list);
            })
            .catch(() => {
                if (!cancelled) setError("Unable to load comments.");
            });
        return () => {
            cancelled = true;
        };
    }, [taskId, tick]);

    async function run(fn: () => Promise<void>) {
        try {
            setBusy(true);
            setError(null);
            await fn();
            load();
        } catch (err) {
            setError(err instanceof Error ? err.message : "That didn't work.");
        } finally {
            setBusy(false);
        }
    }

    const add = (e: React.FormEvent) => {
        e.preventDefault();
        if (!draft.trim()) return;
        void run(async () => {
            await WorkService.addComment(taskId, draft.trim());
            setDraft("");
        });
    };

    return (
        <section className="rounded-xl border p-5">
            <h2 className="font-semibold">Comments</h2>

            {comments.length === 0 && <p className="mt-3 text-sm text-muted-foreground">No comments yet.</p>}

            <ul className="mt-3 space-y-3">
                {comments.map((c) => (
                    <li key={c.id} className="rounded-lg border p-3 text-sm">
                        {editingId === c.id ? (
                            <div className="space-y-2">
                                <textarea
                                    value={editText}
                                    onChange={(e) => setEditText(e.target.value)}
                                    maxLength={5000}
                                    rows={3}
                                    aria-label="Edit comment"
                                    className="w-full rounded-md border bg-background p-2"
                                />
                                <div className="flex gap-2">
                                    <button
                                        type="button"
                                        disabled={busy || !editText.trim()}
                                        onClick={() =>
                                            run(async () => {
                                                await WorkService.editComment(c.id, editText.trim());
                                                setEditingId(null);
                                            })
                                        }
                                        className="rounded-md bg-primary px-3 py-1 text-primary-foreground disabled:opacity-50"
                                    >
                                        Save
                                    </button>
                                    <button type="button" onClick={() => setEditingId(null)} className="rounded-md border px-3 py-1">
                                        Cancel
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <>
                                <p className="whitespace-pre-wrap break-words">{c.body}</p>
                                <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                                    <span>
                                        {new Date(c.created_at).toLocaleString()}
                                        {c.edited ? " · edited" : ""}
                                    </span>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setEditingId(c.id);
                                            setEditText(c.body);
                                        }}
                                        className="hover:underline"
                                    >
                                        Edit
                                    </button>
                                    <button
                                        type="button"
                                        disabled={busy}
                                        onClick={() => {
                                            if (window.confirm("Delete this comment?")) {
                                                void run(() => WorkService.deleteComment(c.id));
                                            }
                                        }}
                                        className="hover:underline"
                                    >
                                        Delete
                                    </button>
                                </div>
                            </>
                        )}
                    </li>
                ))}
            </ul>

            <form onSubmit={add} className="mt-4 space-y-2">
                <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    maxLength={5000}
                    rows={3}
                    aria-label="Add a comment"
                    placeholder="Add a comment…"
                    className="w-full rounded-md border bg-background p-2 text-sm"
                />
                <button
                    type="submit"
                    disabled={busy || !draft.trim()}
                    className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                    Comment
                </button>
            </form>
            {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
        </section>
    );
}
