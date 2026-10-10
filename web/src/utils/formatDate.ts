import { format, formatDistanceToNow, parseISO } from "date-fns";

export function formatDate(dateString: string, formatStr = "MMM d, yyyy"): string {
    try {
        const date = typeof dateString === "string" ? parseISO(dateString) : dateString;
        return format(date, formatStr);
    } catch {
        return dateString;
    }
}

export function formatRelativeTime(dateString: string): string {
    try {
        const date = typeof dateString === "string" ? parseISO(dateString) : dateString;
        return formatDistanceToNow(date, { addSuffix: true });
    } catch {
        return dateString;
    }
}
