"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Beaker, Settings2, BarChart3, Cpu, ScanLine } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview", icon: Activity },
  { href: "/dashboard/production", label: "Production", icon: BarChart3 },
  { href: "/dashboard/srp", label: "SRP Health", icon: Cpu },
  { href: "/dashboard/dynacards", label: "Dynacards", icon: ScanLine },
  { href: "/dashboard/optimize", label: "Optimize", icon: Settings2 },
  { href: "/dashboard/simulate", label: "What-If", icon: Beaker },
];

export function TopNav() {
  const pathname = usePathname();

  return (
    <header className="border-b border-border bg-card/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6 flex items-center justify-between h-14">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-accent flex items-center justify-center">
              <Activity className="h-5 w-5 text-accent-foreground" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight">Tejas</h1>
              <p className="text-[10px] text-muted-foreground leading-none">
                Heavy-Oil Digital Twin
              </p>
            </div>
          </div>
        </div>

        {/* Navigation tabs */}
        <nav className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => {
            const isActive =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  isActive
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Status indicator */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <div className="h-2 w-2 rounded-full bg-safe animate-pulse" />
          <span className="hidden sm:inline">BGW-01</span>
        </div>
      </div>
    </header>
  );
}
