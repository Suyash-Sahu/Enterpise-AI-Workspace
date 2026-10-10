import { apiClient, ApiResponse } from "@/lib/api-client";

/**
 * Google connector client.
 *
 * Every method here used to swallow failures and return invented data — fake
 * Drive files, fake Gmail messages, and a sendEmail that reported "SENT" when
 * the send had failed. Errors now propagate so the UI can show a real error
 * state and a failed send is never reported as delivered.
 */

export interface GoogleDriveFile {
    id: string;
    name: string;
    mimeType: string;
    size?: string;
    modifiedTime?: string;
    webViewLink?: string;
    iconLink?: string;
}

export interface GmailMessage {
    id: string;
    threadId: string;
    from?: string;
    to?: string;
    subject?: string;
    snippet?: string;
    body?: string;
    date?: string;
    internalDate?: string;
}

export interface GmailLabel {
    id: string;
    name: string;
    type?: string;
}

export interface GmailProfile {
    emailAddress: string;
    messagesTotal?: number;
    threadsTotal?: number;
    historyId?: string;
}

export interface GmailThread {
    id: string;
    snippet?: string;
    historyId?: string;
}

export const googleService = {
    /**
     * Start connecting Gmail/Drive to the signed-in account.
     *
     * The backend returns the authorization URL as JSON rather than a redirect,
     * so this request can carry the caller's bearer token — a plain browser
     * redirect could not be authenticated, which is what previously let anyone
     * bind a Google account to the workspace.
     */
    async startGoogleConnect(): Promise<void> {
        const res = await apiClient.get<ApiResponse<{ authorization_url: string }>>(
            "/connectors/google/login"
        );

        const url = res.data?.data?.authorization_url;

        if (!url) {
            throw new Error("Could not start Google connection");
        }

        window.location.href = url;
    },

    /**
     * Connection status.
     *
     * This used to swallow every failure into `{ connected: false }`, so a 401,
     * a 502 or an unreachable backend all rendered as a confident
     * "Disconnected" badge — the page asserted a fact it had never learned. The
     * caller is a query with an error branch, so the failure is surfaced and
     * the UI can say "could not check" instead of guessing.
     */
    async getGoogleStatus(): Promise<{ connected: boolean; email?: string }> {
        const res = await apiClient.get<ApiResponse<{ connected: boolean; email?: string }>>(
            "/connectors/google/status"
        );

        const data = res.data?.data;

        if (!data || typeof data.connected !== "boolean") {
            throw new Error("The connector status response was not understood.");
        }

        return data;
    },

    /**
     * Build a placeholder Meet URL for a calendar entry.
     *
     * KNOWN LIMITATION: this does not create a real conference. Doing that
     * requires the Calendar API with a conferenceData request, which is not
     * implemented — the returned link will not resolve to a live meeting.
     */
    async generateMeetLink(eventTitle: string): Promise<string> {
        const slug = eventTitle
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .slice(0, 12);
        return `https://meet.google.com/${slug || "amof-sync"}`;
    },

    async fetchDriveFiles(): Promise<GoogleDriveFile[]> {
        const res = await apiClient.get<ApiResponse<{ count: number; files: GoogleDriveFile[] }>>(
            "/connectors/google/drive/files"
        );
        return res.data?.data?.files ?? [];
    },

    async searchDriveFiles(query: string): Promise<GoogleDriveFile[]> {
        const res = await apiClient.get<ApiResponse<{ count: number; files: GoogleDriveFile[] }>>(
            `/connectors/google/drive/search?q=${encodeURIComponent(query)}`
        );
        return res.data?.data?.files ?? [];
    },

    async getRecentDriveFiles(limit = 10): Promise<GoogleDriveFile[]> {
        const res = await apiClient.get<ApiResponse<{ count: number; files: GoogleDriveFile[] }>>(
            `/connectors/google/drive/recent?limit=${limit}`
        );
        return res.data?.data?.files ?? [];
    },

    async getDriveFolders(): Promise<GoogleDriveFile[]> {
        const res = await apiClient.get<ApiResponse<{ folders: GoogleDriveFile[] }>>(
            "/connectors/google/drive/folders"
        );
        return res.data?.data?.folders ?? [];
    },

    async getDriveFileDetails(fileId: string): Promise<GoogleDriveFile> {
        const res = await apiClient.get<ApiResponse<GoogleDriveFile>>(
            `/connectors/google/drive/file/${encodeURIComponent(fileId)}`
        );

        if (!res.data?.data) {
            throw new Error("File details unavailable");
        }

        return res.data.data;
    },

    async fetchGmailMessages(): Promise<GmailMessage[]> {
        const res = await apiClient.get<ApiResponse<{ count: number; messages: GmailMessage[] }>>(
            "/connectors/google/gmail/messages"
        );
        return res.data?.data?.messages ?? [];
    },

    async searchGmail(query: string): Promise<GmailMessage[]> {
        const res = await apiClient.get<ApiResponse<{ count: number; results: GmailMessage[] }>>(
            `/connectors/google/gmail/search?q=${encodeURIComponent(query)}`
        );
        return res.data?.data?.results ?? [];
    },

    async fetchUnreadGmail(limit = 20): Promise<GmailMessage[]> {
        const res = await apiClient.get<ApiResponse<{ count: number; emails: GmailMessage[] }>>(
            `/connectors/google/gmail/unread?limit=${limit}`
        );
        return res.data?.data?.emails ?? [];
    },

    async fetchGmailThreads(): Promise<GmailThread[]> {
        const res = await apiClient.get<ApiResponse<{ count: number; threads: GmailThread[] }>>(
            "/connectors/google/gmail/threads"
        );
        return res.data?.data?.threads ?? [];
    },

    async fetchGmailLabels(): Promise<GmailLabel[]> {
        const res = await apiClient.get<ApiResponse<{ labels: GmailLabel[] }>>(
            "/connectors/google/gmail/labels"
        );
        return res.data?.data?.labels ?? [];
    },

    async fetchGmailProfile(): Promise<GmailProfile> {
        const res = await apiClient.get<ApiResponse<GmailProfile>>(
            "/connectors/google/gmail/profile"
        );

        if (!res.data?.data?.emailAddress) {
            throw new Error("Gmail profile unavailable");
        }

        return res.data.data;
    },

    /**
     * Send mail.
     *
     * Requires an approved approval record — the backend rejects the call
     * without one. Errors propagate: reporting a delivery that did not happen
     * is worse than showing a failure.
     */
    async sendEmail(
        to: string,
        subject: string,
        body: string,
        approvalId: number
    ): Promise<{ status: string }> {
        const res = await apiClient.post<ApiResponse<{ status: string }>>(
            "/connectors/google/gmail/send",
            { to, subject, body, approval_id: approvalId }
        );

        // A missing body means we do not know whether the mail went out.
        // Defaulting to "SENT" here reported a delivery nobody confirmed.
        if (!res.data?.data) {
            throw new Error("Gmail did not confirm the send. Check your inbox before resending.");
        }

        return res.data.data;
    },

    async saveDraft(to: string, subject: string, body: string): Promise<{ status: string }> {
        const res = await apiClient.post<ApiResponse<{ status: string }>>(
            "/connectors/google/gmail/draft",
            { to, subject, body }
        );

        if (!res.data?.data) {
            throw new Error("Gmail did not confirm the draft was saved.");
        }

        return res.data.data;
    },
};
