// Shape returned by Google Calendar's own API (passed through by the backend
// as-is -- see app/connectors/google/calendar.py), not a shape we invent.
export interface CalendarEventDTO {
    id: string;
    summary?: string;
    description?: string;
    start?: { dateTime?: string; date?: string };
    end?: { dateTime?: string; date?: string };
    hangoutLink?: string;
    htmlLink?: string;
    attendees?: { email: string; responseStatus?: string }[];
}

export interface CalendarEventCreate {
    summary: string;
    start: string;
    end: string;
    description?: string;
    attendees?: string[];
    add_meet?: boolean;
}
