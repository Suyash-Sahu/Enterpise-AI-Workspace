import { create } from "zustand";
import { SEED_NOTIFICATIONS, CentralNotification } from "@/data/central-store";

interface NotificationState {
    notifications: CentralNotification[];
    unreadCount: number;
    markAsRead: (id: string) => void;
    markAllAsRead: () => void;
}

export const useNotificationStore = create<NotificationState>((set) => ({
    notifications: SEED_NOTIFICATIONS,
    unreadCount: SEED_NOTIFICATIONS.filter((n) => !n.read).length,
    markAsRead: (id) =>
        set((state) => {
            const updated = state.notifications.map((n) => (n.id === id ? { ...n, read: true } : n));
            return {
                notifications: updated,
                unreadCount: updated.filter((n) => !n.read).length,
            };
        }),
    markAllAsRead: () =>
        set((state) => ({
            notifications: state.notifications.map((n) => ({ ...n, read: true })),
            unreadCount: 0,
        })),
}));
