export const ROLES = {
    OWNER: "Owner",
    ADMIN: "Admin",
    MANAGER: "Manager",
    DEVELOPER: "Developer",
    VIEWER: "Viewer",
} as const;

export type RoleType = keyof typeof ROLES;
