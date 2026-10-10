import { apiClient, ApiResponse } from "@/lib/api-client";
import type { GoogleDriveFile, GmailMessage } from "@/services/google.service";

export interface WorkspaceDashboardData {
    user: {
        name: string;
        /** Null when the account has no address on file. */
        email: string | null;
        /** "Google" once a Google account is connected, otherwise "Local". */
        provider: string;
    };
    drive: {
        /** Number of files in `recent`, not a total — Drive has no cheap count. */
        count: number;
        recent: GoogleDriveFile[];
    };
    gmail: {
        /** Real mailbox total from the Gmail profile. */
        count: number;
        /** Real unread count from the UNREAD label. */
        unread: number;
        latest: GmailMessage[];
    };
    ai: {
        local_model: string;
        cloud_model: string;
        /** "unknown" — nothing probes the model runtimes yet. */
        local_status: string;
        cloud_status: string;
    };
    workspace: {
        connected: boolean;
        last_sync: string;
        /** Sections whose data could not be loaded, e.g. ["gmail"]. */
        unavailable: string[];
    };
    capabilities: Record<string, boolean>;
}

export const workspaceService = {
    async getDashboard(): Promise<WorkspaceDashboardData> {
        const res = await apiClient.get<ApiResponse<WorkspaceDashboardData>>("/workspace/dashboard");
        return res.data.data;
    },
};
