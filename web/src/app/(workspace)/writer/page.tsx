"use client";

import { useState } from "react";
import PageHeader from "@/components/shared/PageHeader";
import { useGenerateAIWriter } from "@/hooks/useAIWriter";
import { Sparkles, Copy, Check, RefreshCw, Mail, Edit3, MessageSquare } from "lucide-react";

export default function WriterPage() {
    const [mode, setMode] = useState<"email" | "rewrite" | "reply">("email");
    const [instruction, setInstruction] = useState("");
    const [textToRewrite, setTextToRewrite] = useState("");
    const [emailToReply, setEmailToReply] = useState("");
    const [copied, setCopied] = useState(false);
    const [output, setOutput] = useState<string | null>(null);

    const writerMutation = useGenerateAIWriter();

    const handleGenerate = (e: React.FormEvent) => {
        e.preventDefault();
        setOutput(null);

        let payload: any = { type: mode, instruction };
        if (mode === "rewrite") {
            payload.text = textToRewrite;
        } else if (mode === "reply") {
            payload.email = emailToReply;
        }

        writerMutation.mutate(payload, {
            onSuccess: (res) => {
                setOutput(res);
            },
            onError: (err) => {
                setOutput(`Generation failed: ${err.message}`);
            },
        });
    };

    const handleCopy = () => {
        if (!output) return;
        navigator.clipboard.writeText(output);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="AI Content Writer & Assistant"
                description="Draft emails, rewrite document text, and generate professional replies using backend AI endpoints."
                breadcrumbs={[{ label: "Workspace" }, { label: "AI Writer" }]}
            />

            {/* Mode Switcher */}
            <div className="flex items-center gap-2 border-b border-border pb-3">
                {[
                    { id: "email", label: "Draft Email", icon: Mail },
                    { id: "rewrite", label: "Rewrite & Polish", icon: Edit3 },
                    { id: "reply", label: "Professional Reply", icon: MessageSquare },
                ].map((tab) => {
                    const Icon = tab.icon;
                    const isSelected = mode === tab.id;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => {
                                setMode(tab.id as any);
                                setOutput(null);
                            }}
                            className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-semibold transition-all ${
                                isSelected
                                    ? "bg-primary text-primary-foreground shadow-md font-bold"
                                    : "border border-border bg-surface text-muted-foreground hover:bg-muted"
                            }`}
                        >
                            <Icon className="h-4 w-4" />
                            <span>{tab.label}</span>
                        </button>
                    );
                })}
            </div>

            {/* Main Form & Output Grid */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                {/* Input Form */}
                <form onSubmit={handleGenerate} className="rounded-2xl border border-border bg-surface p-6 shadow-sm space-y-4">
                    <div className="flex items-center gap-2 border-b border-border pb-3">
                        <Sparkles className="h-5 w-5 text-primary" />
                        <h3 className="text-sm font-bold text-foreground">
                            {mode === "email" ? "Email Drafting Prompt" : mode === "rewrite" ? "Text to Rewrite" : "Original Email for Reply"}
                        </h3>
                    </div>

                    {mode === "rewrite" && (
                        <div>
                            <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Source Text</label>
                            <textarea
                                required
                                rows={4}
                                value={textToRewrite}
                                onChange={(e) => setTextToRewrite(e.target.value)}
                                placeholder="Paste your text to rewrite..."
                                className="w-full rounded-xl border border-border bg-background p-3 text-xs text-foreground focus:border-primary focus:outline-none font-mono"
                            />
                        </div>
                    )}

                    {mode === "reply" && (
                        <div>
                            <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">Received Email Text</label>
                            <textarea
                                required
                                rows={4}
                                value={emailToReply}
                                onChange={(e) => setEmailToReply(e.target.value)}
                                placeholder="Paste the email body..."
                                className="w-full rounded-xl border border-border bg-background p-3 text-xs text-foreground focus:border-primary focus:outline-none font-mono"
                            />
                        </div>
                    )}

                    <div>
                        <label className="block text-xs font-bold text-muted-foreground uppercase mb-1">
                            {mode === "email" ? "Writing Instructions" : "Tone & Special Guidance"}
                        </label>
                        <textarea
                            required
                            rows={3}
                            value={instruction}
                            onChange={(e) => setInstruction(e.target.value)}
                            placeholder={
                                mode === "email"
                                    ? "e.g., Write a formal email proposing a project deadline extension to Friday..."
                                    : "e.g., Make it more professional, persuasive, and concise..."
                            }
                            className="w-full rounded-xl border border-border bg-background p-3 text-xs text-foreground focus:border-primary focus:outline-none"
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={writerMutation.isPending}
                        className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-2.5 text-xs font-semibold text-primary-foreground shadow-md transition-all disabled:opacity-50"
                    >
                        {writerMutation.isPending ? (
                            <>
                                <RefreshCw className="h-4 w-4 animate-spin" />
                                <span>Generating with AI...</span>
                            </>
                        ) : (
                            <>
                                <Sparkles className="h-4 w-4" />
                                <span>Generate Content</span>
                            </>
                        )}
                    </button>
                </form>

                {/* Response / Markdown Preview Panel */}
                <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm space-y-4 flex flex-col justify-between">
                    <div>
                        <div className="flex items-center justify-between border-b border-border pb-3">
                            <div className="flex items-center gap-2">
                                <Sparkles className="h-5 w-5 text-primary" />
                                <h3 className="text-sm font-bold text-foreground">Markdown Preview & Output</h3>
                            </div>
                            {output && (
                                <button
                                    onClick={handleCopy}
                                    className="flex items-center gap-1.5 rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-muted"
                                >
                                    {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
                                    <span>{copied ? "Copied!" : "Copy Response"}</span>
                                </button>
                            )}
                        </div>

                        <div className="mt-4">
                            {output ? (
                                <div className="rounded-xl border border-primary/20 bg-background p-4 font-mono text-xs text-foreground leading-relaxed whitespace-pre-wrap">
                                    {output}
                                </div>
                            ) : (
                                <div className="rounded-xl border border-dashed border-border p-12 text-center text-xs text-muted-foreground">
                                    Generated email or text will appear here with live markdown formatting and copy support.
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
