import { ROUTES } from "./routes";

export type NavStatus = "live" | "soon" | "beta";

export interface NavItem {
    name: string;
    /** Short label for tight spaces (marketing). Falls back to `name`. */
    label?: string;
    href: string;
    iconName: string;
    status?: NavStatus;
}

export interface NavGroup {
    label: string;
    items: NavItem[];
}

/**
 * Workspace navigation, grouped.
 */
export const NAV_GROUPS: NavGroup[] = [
    {
        label: "Workspace",
        items: [
            {
                name: "Dashboard",
                href: ROUTES.DASHBOARD,
                iconName: "LayoutDashboard",
            },
            {
                name: "Morning Brief",
                href: ROUTES.BRIEF,
                iconName: "Sunrise",
            },
            {
                name: "Commitments",
                href: ROUTES.COMMITMENTS,
                iconName: "Handshake",
            },
            {
                name: "Automations",
                href: ROUTES.AUTOMATIONS,
                iconName: "Zap",
            },
            {
                name: "AI Documents",
                href: ROUTES.DOCUMENTS,
                iconName: "FileText",
            },
        ],
    },

   {
    label: "Work",
    items: [
        {
            name: "Work",
            href: ROUTES.WORK,
            iconName: "SquareKanban",
        },
        {
            name: "My Work",
            href: "/work/my-work",
            iconName: "SquareKanban",
        },
    ],
},

    {
        label: "Connectors",
        items: [
            {
                name: "Google Drive",
                label: "Drive",
                href: ROUTES.DRIVE,
                iconName: "HardDrive",
            },
            {
                name: "Gmail",
                href: ROUTES.GMAIL,
                iconName: "Mail",
                status: "live",
            },
            {
                name: "Google Meet",
                label: "Meet",
                href: ROUTES.MEET,
                iconName: "Video",
                status: "soon",
            },
        ],
    },

    {
        label: "AI",
        items: [
            {
                name: "Workspace Chat",
                href: ROUTES.CHAT,
                iconName: "MessageSquare",
            },
            {
                name: "AI Writer",
                href: ROUTES.WRITER,
                iconName: "Sparkles",
            },
            {
                name: "Database Agent",
                href: "/database",
                iconName: "Database",
                status: "beta",
            },
            {
                name: "AI Execution",
                label: "Execution",
                href: "/execution",
                iconName: "Cpu",
                status: "beta",
            },
            {
                name: "AMOF Supervisor",
                href: "/supervisor",
                iconName: "Bot",
                status: "beta",
            },
            {
                name: "Research & Eval",
                label: "Research",
                href: ROUTES.RESEARCH,
                iconName: "BarChart3",
                status: "beta",
            },
        ],
    },

    {
        label: "Admin",
        items: [
            {
                name: "Workspace Settings",
                label: "Settings",
                href: ROUTES.SETTINGS,
                iconName: "Settings",
            },
        ],
    },
];

/** Flat list, for any consumer that just needs every destination. */
export const MAIN_NAVIGATION: NavItem[] = NAV_GROUPS.flatMap(
    (group) => group.items
);

/** Retained alias. */
export const DASHBOARD_NAV = MAIN_NAVIGATION;

export const MARKETING_NAV = [
    {
        name: "Features",
        label: "Features",
        href: "#features",
    },
    {
        name: "How It Works",
        label: "How It Works",
        href: "#how-it-works",
    },
    {
        name: "Agents",
        label: "Agents",
        href: "#agents",
    },
    {
        name: "Security",
        label: "Security",
        href: "#security",
    },
    {
        name: "Pricing",
        label: "Pricing",
        href: "#pricing",
    },
];