import { CentralUser } from "@/data/central-store";

interface Props {
    users: CentralUser[];
    max?: number;
}

export default function AvatarGroup({ users, max = 4 }: Props) {
    const visible = users.slice(0, max);
    const remaining = users.length - max;

    return (
        <div className="flex items-center -space-x-2 overflow-hidden">
            {visible.map((user) => (
                <div
                    key={user.id}
                    title={`${user.name} (${user.role})`}
                    className="relative flex h-7 w-7 items-center justify-center rounded-full border-2 border-surface bg-primary/20 text-xs font-bold text-primary shrink-0 select-none shadow-sm"
                >
                    {user.avatar ? (
                        <img src={user.avatar} alt={user.name} className="h-full w-full rounded-full object-cover" />
                    ) : (
                        <span>{user.name.charAt(0)}</span>
                    )}
                </div>
            ))}
            {remaining > 0 && (
                <div className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-surface bg-muted text-xs font-bold text-muted-foreground shrink-0 shadow-sm">
                    +{remaining}
                </div>
            )}
        </div>
    );
}
