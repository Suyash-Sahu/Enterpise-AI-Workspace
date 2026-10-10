"use client";

import React from "react";

interface FormInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
}

export function FormInput({ label, error, icon, className = "", ...props }: FormInputProps) {
  return (
    <div className="space-y-1.5 w-full text-left">
      {label && <label className="block text-xs font-semibold text-foreground">{label}</label>}
      <div className="relative flex items-center">
        {icon && <div className="absolute left-3 text-muted-foreground">{icon}</div>}
        <input
          className={`w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-xs text-foreground placeholder-muted-foreground focus:border-primary focus:outline-none ${icon ? "pl-9" : ""} ${className}`}
          {...props}
        />
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

export default FormInput;
