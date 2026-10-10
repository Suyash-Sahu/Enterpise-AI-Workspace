import { ReactNode } from "react";

interface Props {
  title: string;
  subtitle: ReactNode;
  eyebrow?: string;
}

export default function SectionHeading({ title, subtitle, eyebrow }: Props) {
  return (
    <div className="mx-auto mb-12 max-w-2xl text-center">
      {eyebrow && (
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-primary">
          {eyebrow}
        </p>
      )}
      <h2 className="text-3xl font-semibold tracking-tight text-foreground">
        {title}
      </h2>
      <p className="mt-4 text-base leading-relaxed text-muted-foreground">
        {subtitle}
      </p>
    </div>
  );
}
