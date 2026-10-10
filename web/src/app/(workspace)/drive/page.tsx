"use client";

import { useState } from "react";
import PageHeader from "@/components/shared/PageHeader";
import SearchInput from "@/components/shared/SearchInput";
import ConnectorErrorState from "@/components/shared/ConnectorErrorState";
import { useDriveFiles, useRecentDriveFiles, useDriveFolders } from "@/hooks/useDrive";
import { useSummarizeDocument, useAskDocument, useBulletSummary } from "@/hooks/useDocumentAI";
import { FolderKanban, FileText, Search, Clock, Folder, Sparkles, Eye, BrainCircuit, CheckCircle2, MessageSquare } from "lucide-react";

export default function DrivePage() {
    const [search, setSearch] = useState("");
    const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
    const [selectedFile, setSelectedFile] = useState<any | null>(null);
    const [activeTab, setActiveTab] = useState<"all" | "recent" | "folders">("all");
    const [aiResponse, setAiResponse] = useState<string | null>(null);

    const { data: driveFiles, isLoading, isError, error, refetch } = useDriveFiles();
    const { data: recentFiles } = useRecentDriveFiles();
    const { data: folders } = useDriveFolders();

    const summarizeMutation = useSummarizeDocument();
    const askMutation = useAskDocument();
    const bulletMutation = useBulletSummary();

    const fileList = activeTab === "recent" ? (recentFiles || []) : (driveFiles || []);
    const filteredFiles = fileList.filter((f) => f.name.toLowerCase().includes(search.toLowerCase()));

    const handleSummarize = (file: any) => {
        setSelectedFile(file);
        setAiResponse("AI is generating document summary...");
        summarizeMutation.mutate(file.id, {
            onSuccess: (res) => setAiResponse(res),
            onError: (err) => setAiResponse(`Error: ${err.message}`),
        });
    };

    const handleBullets = (file: any) => {
        setSelectedFile(file);
        setAiResponse("AI is generating bullet point summary...");
        bulletMutation.mutate(file.id, {
            onSuccess: (res) => setAiResponse(res),
            onError: (err) => setAiResponse(`Error: ${err.message}`),
        });
    };

    return (
        <div className="space-y-6">
            <PageHeader
                title="Google Drive Vault"
                description="Browse, search, and perform AI actions directly on your Google Drive files."
                breadcrumbs={[{ label: "Workspace" }, { label: "Drive" }]}
            />

            {/* Navigation Tabs & Search */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 border-b border-border pb-4">
                <div className="flex items-center gap-2 overflow-x-auto w-full sm:w-auto">
                    {[
                        { id: "all", label: "All Files", icon: FileText },
                        { id: "recent", label: "Recent Files", icon: Clock },
                        { id: "folders", label: "Folders", icon: Folder },
                    ].map((tab) => {
                        const Icon = tab.icon;
                        const isSelected = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id as any)}
                                className={`flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-semibold transition-all ${
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

                <SearchInput value={search} onChange={setSearch} placeholder="Search..." className="max-w-md w-full" />
            </div>

            {/* Main Content Layout */}
            {isLoading ? (
                <div className="rounded-2xl border border-border bg-surface p-8 text-center text-xs text-muted-foreground animate-pulse">
                    Connecting to Google Drive REST API...
                </div>
            ) : isError ? (
                <ConnectorErrorState
                    error={error}
                    resource="Drive files"
                    onRetry={() => refetch()}
                />
            ) : (
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                    {/* Files List / Cards */}
                    <div className="lg:col-span-2 space-y-4">
                        {activeTab === "folders" ? (
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                {(folders || []).map((folder: any, idx: number) => (
                                    <div key={idx} className="rounded-2xl border border-border bg-surface p-4 flex items-center gap-3 hover:border-primary/40 cursor-pointer">
                                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-warning/10 text-warning border border-warning/20">
                                            <Folder className="h-5 w-5" />
                                        </div>
                                        <div>
                                            <h4 className="text-xs font-bold text-foreground">{folder.name || `Folder ${idx + 1}`}</h4>
                                            <span className="text-xs font-mono text-muted-foreground">Google Drive Directory</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                {filteredFiles.map((file) => {
                                    const isSelected = (selectedFile || filteredFiles[0])?.id === file.id;
                                    return (
                                        <div
                                            key={file.id}
                                            onClick={() => setSelectedFile(file)}
                                            className={`cursor-pointer rounded-2xl border p-4 shadow-sm transition-all space-y-3 ${
                                                isSelected
                                                    ? "border-primary bg-primary/10 shadow-md"
                                                    : "border-border bg-surface hover:border-primary/40"
                                            }`}
                                        >
                                            <div className="flex items-start justify-between">
                                                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-info/10 text-info font-mono text-xs font-bold uppercase border border-info/20">
                                                    DOC
                                                </div>
                                                <span className="rounded-full bg-success/10 px-2.5 py-0.5 font-mono text-xs font-bold text-success border border-success/20">
                                                    Synced
                                                </span>
                                            </div>

                                            <div>
                                                <h4 className="text-xs font-bold text-foreground truncate">{file.name}</h4>
                                                <p className="text-xs font-mono text-muted-foreground truncate">{file.mimeType || "Google Document"}</p>
                                            </div>

                                            {/* AI Actions Row */}
                                            <div className="flex items-center gap-2 pt-2 border-t border-border">
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleSummarize(file);
                                                    }}
                                                    className="flex items-center gap-1 rounded-lg bg-primary/20 px-2.5 py-1 text-xs font-bold text-primary hover:bg-primary hover:text-primary-foreground transition-all"
                                                >
                                                    <Sparkles className="h-3 w-3" />
                                                    <span>Summarize</span>
                                                </button>
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleBullets(file);
                                                    }}
                                                    className="flex items-center gap-1 rounded-lg bg-primary/20 px-2.5 py-1 text-xs font-bold text-primary hover:bg-primary hover:text-primary-foreground transition-all"
                                                >
                                                    <span>Bullets</span>
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    {/* File Inspector & AI Response Chat Panel */}
                    <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4">
                        <div className="flex items-center gap-2 border-b border-border pb-3">
                            <BrainCircuit className="h-5 w-5 text-primary" />
                            <h3 className="text-sm font-bold text-foreground">File AI Inspector</h3>
                        </div>

                        {(selectedFile || filteredFiles[0]) ? (
                            <div className="space-y-4 text-xs">
                                <div>
                                    <span className="font-mono text-xs font-bold text-primary uppercase">Active Drive File</span>
                                    <h4 className="text-sm font-bold text-foreground mt-0.5">{(selectedFile || filteredFiles[0]).name}</h4>
                                    <span className="font-mono text-xs text-muted-foreground">ID: {(selectedFile || filteredFiles[0]).id}</span>
                                </div>

                                <div className="space-y-2">
                                    <button
                                        onClick={() => handleSummarize(selectedFile || filteredFiles[0])}
                                        className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-2 text-xs font-semibold text-primary-foreground shadow-md transition-all"
                                    >
                                        <Sparkles className="h-4 w-4" />
                                        <span>Summarize with AI</span>
                                    </button>
                                    <button
                                        onClick={() => handleBullets(selectedFile || filteredFiles[0])}
                                        className="flex w-full items-center justify-center gap-2 rounded-xl border border-border bg-background py-2 text-xs font-semibold text-foreground hover:bg-muted transition-all"
                                    >
                                        <FileText className="h-4 w-4" />
                                        <span>Bullet Point Highlights</span>
                                    </button>
                                </div>

                                {/* AI Response Output */}
                                {aiResponse ? (
                                    <div className="rounded-xl border border-primary/30 bg-primary/10 p-3 space-y-2">
                                        <div className="flex items-center gap-1.5 text-primary font-bold text-xs">
                                            <Sparkles className="h-4 w-4" />
                                            <span>AI Output</span>
                                        </div>
                                        <p className="text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap font-mono">{aiResponse}</p>
                                    </div>
                                ) : (
                                    <div className="rounded-xl border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                                        Click Summarize or Bullets to view AI generated content here.
                                    </div>
                                )}
                            </div>
                        ) : (
                            <p className="text-xs text-muted-foreground">Select any Google Drive file to view metadata and trigger AI actions.</p>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
