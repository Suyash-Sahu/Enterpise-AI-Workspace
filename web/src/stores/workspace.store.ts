import { create } from "zustand";
import { SEED_WORKSPACE, SEED_USERS, CentralWorkspace, CentralUser } from "@/data/central-store";

interface WorkspaceState {
    currentWorkspace: CentralWorkspace;
    members: CentralUser[];
    selectedWorkspaceId: string;
    setWorkspace: (workspace: CentralWorkspace) => void;
    addMember: (email: string, role: string) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
    currentWorkspace: SEED_WORKSPACE,
    members: SEED_USERS,
    selectedWorkspaceId: SEED_WORKSPACE.id,
    setWorkspace: (workspace) => set({ currentWorkspace: workspace, selectedWorkspaceId: workspace.id }),
    addMember: (email, role) =>
        set((state) => ({
            members: [
                ...state.members,
                {
                    id: `u-${Date.now()}`,
                    name: email.split("@")[0],
                    email,
                    role,
                    avatar: "",
                    status: "online",
                    department: "Engineering",
                },
            ],
        })),
}));
