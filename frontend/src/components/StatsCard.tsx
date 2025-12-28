"use client";

import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";

interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: LucideIcon;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  variant?: "default" | "success" | "warning" | "danger";
}

export function StatsCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendValue,
  variant = "default",
}: StatsCardProps) {
  const variantStyles = {
    default: "border-border",
    success: "border-grade-a/50 glow-green",
    warning: "border-grade-c/50 glow-amber",
    danger: "border-grade-f/50 glow-red",
  };

  const iconStyles = {
    default: "text-muted-foreground",
    success: "text-grade-a",
    warning: "text-grade-c",
    danger: "text-grade-f",
  };

  return (
    <div
      className={cn(
        "rounded-xl border bg-card p-6 card-hover",
        variantStyles[variant]
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="mt-2 text-3xl font-bold">{value}</p>
          {subtitle && (
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          )}
          {trend && trendValue && (
            <p
              className={cn(
                "mt-2 text-sm",
                trend === "up" && "text-grade-f",
                trend === "down" && "text-grade-a",
                trend === "neutral" && "text-muted-foreground"
              )}
            >
              {trend === "up" ? "↑" : trend === "down" ? "↓" : "→"} {trendValue}
            </p>
          )}
        </div>
        {Icon && (
          <div
            className={cn(
              "rounded-lg bg-muted p-3",
              iconStyles[variant]
            )}
          >
            <Icon className="h-6 w-6" />
          </div>
        )}
      </div>
    </div>
  );
}

