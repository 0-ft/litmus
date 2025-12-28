"use client";

import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, Assessment } from "@/lib/api";
import { RiskBadge } from "@/components/RiskBadge";
import { formatDate, sourceLabel } from "@/lib/utils";
import Link from "next/link";
import { AlertTriangle, ExternalLink } from "lucide-react";

export default function FlaggedPage() {
  const { data: flagged, isLoading } = useQuery({
    queryKey: ["flagged"],
    queryFn: assessmentsApi.flagged,
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="rounded-lg bg-destructive/20 p-3">
          <AlertTriangle className="h-6 w-6 text-destructive" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Flagged Papers</h1>
          <p className="text-muted-foreground">
            Papers requiring human review due to high biosecurity risk scores
          </p>
        </div>
      </div>

      {/* Warning banner */}
      {flagged && flagged.length > 0 && (
        <div className="rounded-xl border border-destructive/50 bg-destructive/10 p-4">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            <p className="text-sm">
              <strong>{flagged.length} papers</strong> have been flagged for
              potential biosecurity concerns. Please review each assessment
              carefully.
            </p>
          </div>
        </div>
      )}

      {/* Flagged list */}
      {isLoading ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
          Loading flagged papers...
        </div>
      ) : flagged && flagged.length > 0 ? (
        <div className="space-y-4">
          {flagged.map((assessment: Assessment) => (
            <div
              key={assessment.id}
              className="rounded-xl border border-destructive/30 bg-card p-6 hover:border-destructive/50 transition-colors"
            >
              <div className="flex items-start gap-4">
                <RiskBadge
                  grade={assessment.risk_grade}
                  size="lg"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-muted-foreground">
                      {sourceLabel(assessment.paper_source || "")} •{" "}
                      {assessment.paper_external_id}
                    </span>
                  </div>
                  <Link
                    href={`/papers/${assessment.paper_id}`}
                    className="text-lg font-medium hover:text-primary transition-colors"
                  >
                    {assessment.paper_title}
                  </Link>
                  
                  {/* Flag reason */}
                  {assessment.flag_reason && (
                    <div className="mt-3 rounded-lg bg-destructive/10 p-3">
                      <p className="text-sm text-destructive">
                        <strong>Flagged:</strong> {assessment.flag_reason}
                      </p>
                    </div>
                  )}

                  {/* Concerns summary */}
                  {assessment.concerns_summary && (
                    <p className="mt-3 text-sm text-muted-foreground">
                      {assessment.concerns_summary}
                    </p>
                  )}

                  {/* Scores */}
                  <div className="mt-4 flex flex-wrap gap-4 text-sm">
                    <span>
                      Overall:{" "}
                      <strong>{assessment.overall_score.toFixed(1)}</strong>
                    </span>
                    <span className="text-muted-foreground">
                      Pathogen: {assessment.pathogen_score.toFixed(0)}
                    </span>
                    <span className="text-muted-foreground">
                      GoF: {assessment.gof_score.toFixed(0)}
                    </span>
                    <span className="text-muted-foreground">
                      Containment: {assessment.containment_score.toFixed(0)}
                    </span>
                    <span className="text-muted-foreground">
                      Dual-use: {assessment.dual_use_score.toFixed(0)}
                    </span>
                  </div>

                  {/* Meta */}
                  <div className="mt-4 flex items-center gap-4 text-xs text-muted-foreground">
                    <span>Assessed: {formatDate(assessment.assessed_at)}</span>
                    {assessment.model_version && (
                      <span>Model: {assessment.model_version}</span>
                    )}
                  </div>
                </div>
                <Link
                  href={`/papers/${assessment.paper_id}`}
                  className="rounded-lg bg-muted px-4 py-2 text-sm font-medium hover:bg-muted/80 transition-colors"
                >
                  View Details
                </Link>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card p-8 text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-grade-a/20 flex items-center justify-center mb-4">
            <AlertTriangle className="h-6 w-6 text-grade-a" />
          </div>
          <h3 className="font-medium mb-2">No Flagged Papers</h3>
          <p className="text-muted-foreground">
            No papers have been flagged for biosecurity concerns yet.
          </p>
        </div>
      )}
    </div>
  );
}

