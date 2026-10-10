"use client";

import { useState } from "react";
import { X, Calendar as CalendarIcon, Video, Sparkles } from "lucide-react";
import { CentralEvent } from "@/data/central-store";

interface Props {
    isOpen: boolean;
    onClose: () => void;
    onCreate: (event: { title: string; date: string; time: string; category: CentralEvent["category"]; addMeet: boolean }) => void;
}

export default function CreateEventModal({ isOpen, onClose, onCreate }: Props) {
    const [title, setTitle] = useState("");
    const [date, setDate] = useState("2026-08-05");
    const [time, setTime] = useState("10:00 AM");
    const [category, setCategory] = useState<CentralEvent["category"]>("Meeting");
    const [addMeet, setAddMeet] = useState(true);

    if (!isOpen) return null;

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!title.trim()) return;

        onCreate({ title, date, time, category, addMeet });
        onClose();
        setTitle("");
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in">
            <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-border bg-surface p-6 shadow-md space-y-4">
                <div className="flex items-center justify-between border-b border-border pb-3">
                    <div className="flex items-center gap-2">
                        <CalendarIcon className="h-5 w-5 text-primary" />
                        <h3 className="text-sm font-bold text-foreground">Create Meeting or Event</h3>
                    </div>
                    <button onClick={onClose} className="rounded-lg p-1 text-muted-foreground hover:bg-muted">
                        <X className="h-4 w-4" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4 text-xs">
                    <div className="space-y-1">
                        <label className="block font-semibold text-foreground">Event Title</label>
                        <input
                            type="text"
                            placeholder="e.g. AMOF Architecture Review Sync"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                            required
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                            <label className="block font-semibold text-foreground">Date</label>
                            <input
                                type="date"
                                value={date}
                                onChange={(e) => setDate(e.target.value)}
                                className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                            />
                        </div>

                        <div className="space-y-1">
                            <label className="block font-semibold text-foreground">Time</label>
                            <input
                                type="text"
                                value={time}
                                onChange={(e) => setTime(e.target.value)}
                                className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                            />
                        </div>
                    </div>

                    <div className="space-y-1">
                        <label className="block font-semibold text-foreground">Category</label>
                        <select
                            value={category}
                            onChange={(e) => setCategory(e.target.value as any)}
                            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                        >
                            <option value="Meeting">Meeting</option>
                            <option value="Sprint">Sprint Sync</option>
                            <option value="Deployment">Deployment</option>
                            <option value="Reminder">Reminder</option>
                            <option value="Deadline">Deadline</option>
                        </select>
                    </div>

                    <div className="flex items-center gap-2 rounded-xl border border-success/30 bg-success/10 p-3">
                        <input
                            type="checkbox"
                            id="meetToggle"
                            checked={addMeet}
                            onChange={(e) => setAddMeet(e.target.checked)}
                            className="h-4 w-4 rounded border-success/50 text-success"
                        />
                        <label htmlFor="meetToggle" className="flex items-center gap-1.5 text-xs font-bold text-success cursor-pointer">
                            <Video className="h-4 w-4" />
                            <span>Auto-generate Google Meet Video Call Link</span>
                        </label>
                    </div>

                    <div className="flex items-center justify-end gap-2 pt-2">
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
                            <Sparkles className="h-3.5 w-3.5" />
                            <span>Schedule Event</span>
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
