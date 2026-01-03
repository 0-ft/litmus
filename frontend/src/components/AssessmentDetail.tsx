"use client";

import { useState } from "react";
import { Assessment } from "@/lib/api";
import { RiskBadge, ScoreBar } from "./RiskBadge";
import { cn, formatDate } from "@/lib/utils";
import { AlertTriangle, Shield, Biohazard, FlaskConical, Users, ChevronDown, ChevronRight, Bug, FileText, MessageSquare } from "lucide-react";

interface AssessmentDetailProps {
  assessment: Assessment;
}

export function AssessmentDetail({ assessment }: AssessmentDetailProps) {
  const [showDebug, setShowDebug] = useState(false);
  
  const rationale = assessment.rationale ? JSON.parse(assessment.rationale) : null;
  const pathogens = assessment.pathogens_identified
    ? JSON.parse(assessment.pathogens_identified)
    : [];
  
  // Parse debug data
  const inputPrompt = assessment.input_prompt ? JSON.parse(assessment.input_prompt) : null;
  const rawOutput = assessment.raw_output;

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
                
                {/* Facility References */}
                {rationale.containment_analysis.facilities_referenced?.length > 0 && (
                  <div className="mt-3 space-y-2">
                    <h5 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Facilities Referenced</h5>
                    <div className="space-y-2">
                      {rationale.containment_analysis.facilities_referenced.map((facility: any, idx: number) => (
                        <div key={idx} className="rounded-lg bg-muted/50 p-3 text-sm">
                          <div className="flex items-center justify-between">
                            <span className="font-medium">{facility.name}</span>
                            <span className={`text-xs px-2 py-0.5 rounded ${
                              facility.adequate_for_work 
                                ? 'bg-green-500/20 text-green-700 dark:text-green-400' 
                                : 'bg-red-500/20 text-red-700 dark:text-red-400'
                            }`}>
                              {facility.adequate_for_work ? '✓ Adequate' : '⚠ Concern'}
                            </span>
                          </div>
                          <div className="mt-1 text-muted-foreground">
                            <span>BSL: {facility.stated_bsl}</span>
                            <span className="mx-2">•</span>
                            <span>Source: {facility.source}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
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

      {/* Debug View */}
      {(inputPrompt || rawOutput) && (
        <div className="rounded-lg border border-border bg-card">
          <button
            onClick={() => setShowDebug(!showDebug)}
            className="flex items-center gap-2 w-full p-4 text-left hover:bg-muted/50 transition-colors"
          >
            {showDebug ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
            <Bug className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">Debug View</span>
            <span className="text-xs text-muted-foreground ml-2">
              (Full assessment trace)
            </span>
          </button>
          
          {showDebug && (
            <div className="border-t border-border p-4 space-y-6">
              {/* Input Prompt */}
              {inputPrompt && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-blue-500" />
                    <h4 className="font-medium">Input to Model</h4>
                  </div>
                  
                  {/* System Prompt */}
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      System Prompt
                    </label>
                    <pre className="bg-muted/50 rounded-lg p-3 text-xs overflow-x-auto max-h-64 overflow-y-auto whitespace-pre-wrap font-mono">
                      {inputPrompt.system}
                    </pre>
                  </div>
                  
                  {/* User Prompt */}
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      User Prompt
                    </label>
                    <pre className="bg-muted/50 rounded-lg p-3 text-xs overflow-x-auto max-h-96 overflow-y-auto whitespace-pre-wrap font-mono">
                      {inputPrompt.user}
                    </pre>
                  </div>
                  
                  {/* Model & Format */}
                  <div className="flex gap-4 text-xs text-muted-foreground">
                    <span>Model: <code className="bg-muted px-1 rounded">{inputPrompt.model}</code></span>
                    <span>Format: <code className="bg-muted px-1 rounded">{inputPrompt.output_format}</code></span>
                  </div>
                </div>
              )}
              
              {/* Raw Output */}
              {rawOutput && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4 text-green-500" />
                    <h4 className="font-medium">Raw Model Output</h4>
                  </div>
                  <pre className="bg-muted/50 rounded-lg p-3 text-xs overflow-x-auto max-h-96 overflow-y-auto whitespace-pre-wrap font-mono">
                    {typeof rawOutput === 'string' 
                      ? (rawOutput.startsWith('{') 
                          ? JSON.stringify(JSON.parse(rawOutput), null, 2)
                          : rawOutput)
                      : JSON.stringify(rawOutput, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

