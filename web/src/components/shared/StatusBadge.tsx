import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";

interface Props {
  status: "success" | "warning" | "error";
  label: string;
}

const variant = {
  success: "success",
  warning: "warning",
  error: "destructive",
} as const;

const icons = {
  success: CheckCircle2,
  warning: AlertTriangle,
  error: XCircle,
};

export default function StatusBadge({ status, label }: Props) {
  const Icon = icons[status];

  return (
    <Badge variant={variant[status]} className="gap-1.5">
      <Icon aria-hidden />
      {label}
    </Badge>
  );
}
