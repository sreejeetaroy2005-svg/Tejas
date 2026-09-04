"use client";

import { Info } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface InfoTooltipProps {
  text: string;
}

export function InfoTooltip({ text }: InfoTooltipProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors ml-1.5 focus:outline-none"
        >
          <Info className="h-3.5 w-3.5" />
          <span className="sr-only">Information</span>
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-[280px] leading-relaxed text-center">
        {text}
      </TooltipContent>
    </Tooltip>
  );
}
