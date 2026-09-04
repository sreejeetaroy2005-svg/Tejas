"use client";

import { useState } from "react";
import { X, Info } from "lucide-react";

interface IntroBannerProps {
  message: string;
}

export function IntroBanner({ message }: IntroBannerProps) {
  const [isVisible, setIsVisible] = useState(true);

  if (!isVisible) return null;

  return (
    <div className="relative mb-6 rounded-lg border border-accent/20 bg-accent/5 px-4 py-3 shadow-sm">
      <div className="flex items-start gap-3">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
        <div className="flex-1 text-sm text-foreground">
          {message}
        </div>
        <button
          onClick={() => setIsVisible(false)}
          className="text-muted-foreground hover:text-foreground transition-colors focus:outline-none"
          aria-label="Dismiss banner"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
