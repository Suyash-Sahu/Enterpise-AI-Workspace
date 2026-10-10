import { create } from "zustand";
import { ThemeMode } from "@/constants/theme";

interface SettingsState {
    theme: ThemeMode;
    accentColor: string;
    density: "compact" | "comfortable" | "spacious";
    executionMode: "Local" | "Cloud" | "Hybrid";
    streamingEnabled: boolean;
    showCitations: boolean;
    showAgentTimeline: boolean;
    setTheme: (theme: ThemeMode) => void;
    setAccentColor: (color: string) => void;
    setDensity: (density: "compact" | "comfortable" | "spacious") => void;
    setExecutionMode: (mode: "Local" | "Cloud" | "Hybrid") => void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
    theme: "dark",
    accentColor: "#4F46E5",
    density: "comfortable",
    executionMode: "Hybrid",
    streamingEnabled: true,
    showCitations: true,
    showAgentTimeline: true,
    setTheme: (theme) => set({ theme }),
    setAccentColor: (color) => set({ accentColor: color }),
    setDensity: (density) => set({ density }),
    setExecutionMode: (mode) => set({ executionMode: mode }),
}));
