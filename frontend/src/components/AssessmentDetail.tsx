"use client";

import { Assessment } from "@/lib/api";
import { RiskBadge, ScoreBar } from "./RiskBadge";
import { cn, formatDate } from "@/lib/utils";
import { AlertTriangle, Shield, Biohazard, FlaskConical, Users } from "lucide-react";

interface AssessmentDetailProps {
  assessment: Assessment;
}

export function AssessmentDetail({ assessment }: AssessmentDetailProps) {
  const rationale = assessment.rationale ? JSON.parse(assessment.rationale) : null;
  const pathogens = assessment.pathogens_identified
    ? JSON.parse(assessment.pathogens_identified)
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <RiskBadge grade={assessment.risk_grade} size="lg" />
          <div>
            <h2 className="text-xl font-bold">
              Risk Grade: {assessment.risk_grade}
            </h2>
            <p className="text-muted-foreground">
              Overall Score: {assessment.overall_score.toFixed(1)} / 100
            </p>
          </div>
        </div>
        {assessment.flagged && (
          <div className="flex items-center gap-2 rounded-lg bg-destructive/20 px-4 py-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            <span className="font-medium">Flagged for Review</span>
          </div>
        )}
      </div>

      {/* Concerns Summary */}
      {assessment.concerns_summary && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="font-medium mb-2">Summary</h3>
          <p className="text-muted-foreground">{assessment.concerns_summary}</p>
        </div>
      )}

      {/* Score Breakdown */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h3 className="font-medium mb-4">Risk Score Breakdown</h3>
        <div className="grid gap-4">
          <div className="flex items-center gap-4">
            <Biohazard className="h-5 w-5 text-muted-foreground" />
            <div className="flex-1">
              <ScoreBar label="Pathogen Risk" score={assessment.pathogen_score} />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <FlaskConical className="h-5 w-5 text-muted-foreground" />
            <div className="flex-1">
              <ScoreBar label="Gain-of-Function" score={assessment.gof_score} />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Shield className="h-5 w-5 text-muted-foreground" />
            <div className="flex-1">
              <ScoreBar label="Containment Concern" score={assessment.containment_score} />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Users className="h-5 w-5 text-muted-foreground" />
            <div className="flex-1">
              <ScoreBar label="Dual-Use Concern" score={assessment.dual_use_score} />
            </div>
          </div>
        </div>
      </div>

      {/* Pathogens Identified */}
      {pathogens.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-6">
          <h3 className="font-medium mb-4">Pathogens Identified</h3>
          <div className="flex flex-wrap gap-2">
            {pathogens.map((pathogen: string, idx: number) => (
              <span
                key={idx}
                className="rounded-full bg-destructive/20 px-3 py-1 text-sm text-destructive"
              >
                {pathogen}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Detailed Analysis */}
      {rationale && (
        <div className="rounded-lg border border-border bg-card p-6">
          <h3 className="font-medium mb-4">Detailed Analysis</h3>
          <div className="space-y-4 text-sm">
            {rationale.pathogen_analysis?.rationale && (
              <div>
                <h4 className="font-medium text-muted-foreground">Pathogen Analysis</h4>
                <p className="mt-1">{rationale.pathogen_analysis.rationale}</p>
              </div>
            )}
            {rationale.gof_analysis?.rationale && (
              <div>
                <h4 className="font-medium text-muted-foreground">Gain-of-Function Analysis</h4>
                <p className="mt-1">{rationale.gof_analysis.rationale}</p>
              </div>
            )}
            {rationale.containment_analysis?.rationale && (
              <div>
                <h4 className="font-medium text-muted-foreground">Containment Analysis</h4>
                <p className="mt-1">{rationale.containment_analysis.rationale}</p>
              </div>
            )}
            {rationale.dual_use_analysis?.rationale && (
              <div>
                <h4 className="font-medium text-muted-foreground">Dual-Use Analysis</h4>
                <p className="mt-1">{rationale.dual_use_analysis.rationale}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Meta */}
      <div className="flex items-center gap-4 text-sm text-muted-foreground">
        <span>Assessed: {formatDate(assessment.assessed_at)}</span>
        {assessment.model_version && (
          <span>Model: {assessment.model_version}</span>
        )}
      </div>
    </div>
  );
}

