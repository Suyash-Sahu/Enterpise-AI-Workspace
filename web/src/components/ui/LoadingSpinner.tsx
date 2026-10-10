import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

interface Props {
  /** px size of the icon. */
  size?: number;
  /** Screen-reader label; also renders visually when `showLabel`. */
  label?: string;
  showLabel?: boolean;
  className?: string;
}

export default function LoadingSpinner({
  size = 18,
  label = "Loading",
  showLabel = false,
  className,
}: Props) {
  return (
    <span
      role="status"
      aria-live="polite"
      className={cn("inline-flex items-center gap-2 text-muted-foreground", className)}
    >
      <Loader2 className="animate-spin" size={size} aria-hidden />
      {showLabel ? (
        <span className="text-sm">{label}</span>
      ) : (
        <span className="sr-only">{label}</span>
      )}
    </span>
  );
}
