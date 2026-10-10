"use client";

import { useState } from "react";
import { X, Send, Sparkles, Wand2, Paperclip } from "lucide-react";
import { googleService } from "@/services/google.service";

interface Props {
    isOpen: boolean;
    onClose: () => void;
    onSent: (email: { to: string; subject: string; body: string }) => void;
}

export default function ComposeEmailModal({ isOpen, onClose, onSent }: Props) {
    const [to, setTo] = useState("");
    const [subject, setSubject] = useState("");
    const [body, setBody] = useState("");

    const [isRewriting, setIsRewriting] = useState(false);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!to || !subject || !body) return;
        onSent({ to, subject, body });
        onClose();
    };

    const handleAIRewrite = () => {
        if (!body.trim()) return;
        setIsRewriting(true);
        setTimeout(() => {
            setBody((prev) => `Dear Colleague,\n\n${prev.trim()}\n\nBest regards,\nAMOF Writing Agent`);
            setIsRewriting(false);
        }, 800);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in">
            <div className="w-full max-w-2xl overflow-hidden rounded-2xl border border-border bg-surface p-6 shadow-md space-y-4">
                <div className="flex items-center justify-between border-b border-border pb-3">
                    <div className="flex items-center gap-2">
                        <Send className="h-5 w-5 text-primary" />
                        <h3 className="text-sm font-bold text-foreground">Compose Gmail via AMOF Writing Agent</h3>
                    </div>
                    <button onClick={onClose} className="rounded-lg p-1 text-muted-foreground hover:bg-muted">
                        <X className="h-4 w-4" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4 text-xs">
                    <div className="space-y-1">
                        <label className="block font-semibold text-foreground">To</label>
                        <input
                            type="email"
                            placeholder="recipient@enterprise.ai"
                            value={to}
                            onChange={(e) => setTo(e.target.value)}
                            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                            required
                        />
                    </div>

                    <div className="space-y-1">
                        <label className="block font-semibold text-foreground">Subject</label>
                        <input
                            type="text"
                            placeholder="e.g. AMOF Phase 3 Frontend Review Sign-off"
                            value={subject}
                            onChange={(e) => setSubject(e.target.value)}
                            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                            required
                        />
                    </div>

                    <div className="space-y-1">
                        <div className="flex items-center justify-between">
                            <label className="block font-semibold text-foreground">Body</label>
                            <button
                                type="button"
                                onClick={handleAIRewrite}
                                disabled={isRewriting}
                                className="flex items-center gap-1 font-mono text-xs font-bold text-primary hover:underline"
                            >
                                <Wand2 className="h-3 w-3" />
                                <span>{isRewriting ? "AI Professionalizing..." : "AI Professionalize Tone"}</span>
                            </button>
                        </div>
                        <textarea
                            rows={6}
                            placeholder="Draft your email or click AI Professionalize Tone..."
                            value={body}
                            onChange={(e) => setBody(e.target.value)}
                            className="w-full rounded-xl border border-border bg-background p-3 text-xs text-foreground focus:border-primary focus:outline-none leading-relaxed"
                            required
                        />
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-border">
                        <button type="button" className="flex items-center gap-1 font-mono text-xs text-muted-foreground hover:text-foreground">
                            <Paperclip className="h-3.5 w-3.5" />
                            <span>Attach Drive File</span>
                        </button>
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={onClose}
                                className="rounded-xl border border-border bg-surface px-4 py-2 text-xs font-semibold text-foreground hover:bg-muted"
                            >
                                Cancel
                            </button>
                            <button
                                type="submit"
                                className="flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-md"
                            >
                                <span>Send Gmail</span>
                                <Send className="h-3.5 w-3.5" />
                            </button>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    );
}
