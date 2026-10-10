export const ACCENT_COLORS = [
    { name: "Indigo", value: "#4F46E5", class: "bg-indigo-600" },
    { name: "Emerald", value: "#10B981", class: "bg-emerald-600" },
    { name: "Sky", value: "#0EA5E9", class: "bg-sky-600" },
    { name: "Purple", value: "#8B5CF6", class: "bg-purple-600" },
    { name: "Rose", value: "#F43F5E", class: "bg-rose-600" },
    { name: "Amber", value: "#F59E0B", class: "bg-amber-600" },
] as const;

export type ThemeMode = "system" | "light" | "dark";