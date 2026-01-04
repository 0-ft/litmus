"use client";

import { cn, getGradeColor, getGradeBgColor } from "@/lib/utils";

interface RiskBadgeProps {
  grade: string;
  score?: number;
  size?: "sm" | "md" | "lg";
  showScore?: boolean;
}

export function RiskBadge({ grade, score, size = "md", showScore = false }: RiskBadgeProps) {
  const sizeClasses = {
    sm: "h-6 w-6 text-xs",
    md: "h-8 w-8 text-sm",
    lg: "h-12 w-12 text-lg",
  };

  return (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          "flex items-center justify-center rounded-lg border font-bold",
          sizeClasses[size],
          getGradeBgColor(grade),
          getGradeColor(grade),
          grade === "F" && "risk-badge-f"
        )}
      >
        {grade}
      </div>
      {showScore && score !== undefined && (
        <span className={cn("text-sm font-medium", getGradeColor(grade))}>
          {score.toFixed(1)}
        </span>
      )}
    </div>
  );
}

interface ScoreBarProps {
  label: string;
  score: number;
  maxScore?: number;
}

export function ScoreBar({ label, score, maxScore = 10 }: ScoreBarProps) {
  const percentage = (score / maxScore) * 100;
  
  const getBarColor = (score: number) => {
    if (score < 20) return "bg-grade-a";
    if (score < 40) return "bg-grade-b";
    if (score < 60) return "bg-grade-c";
    if (score < 80) return "bg-grade-d";
    return "bg-grade-f";
  };

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{score.toFixed(1)}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full transition-all", getBarColor(score))}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

