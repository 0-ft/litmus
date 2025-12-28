"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, Assessment } from "@/lib/api";
import { RiskBadge } from "@/components/RiskBadge";
import { formatDate, sourceLabel } from "@/lib/utils";
import Link from "next/link";
import { ChevronLeft, ChevronRight, Filter } from "lucide-react";

export default function AssessmentsPage() {
  const [page, setPage] = useState(1);
  const [gradeFilter, setGradeFilter] = useState<string | undefined>();
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["assessments", page, gradeFilter],
    queryFn: () =>
      assessmentsApi.list(page, pageSize, { risk_grade: gradeFilter }),
  });

  const totalPages = Math.ceil((data?.total || 0) / pageSize);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Assessments</h1>
          <p className="text-muted-foreground">
            {data?.total || 0} papers assessed
          </p>
        </div>
        {/* Filters */}
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <select
            value={gradeFilter || ""}
            onChange={(e) => {
              setGradeFilter(e.target.value || undefined);
              setPage(1);
            }}
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
          >
            <option value="">All Grades</option>
            <option value="A">Grade A</option>
            <option value="B">Grade B</option>
            <option value="C">Grade C</option>
            <option value="D">Grade D</option>
            <option value="F">Grade F</option>
          </select>
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
          Loading assessments...
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Risk
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Paper
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Scores
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Date
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data?.assessments.map((assessment: Assessment) => (
                <tr
                  key={assessment.id}
                  className="hover:bg-muted/30 transition-colors"
                >
                  <td className="px-4 py-4">
                    <RiskBadge
                      grade={assessment.risk_grade}
                      score={assessment.overall_score}
                      showScore
                    />
                  </td>
                  <td className="px-4 py-4">
                    <Link
                      href={`/papers/${assessment.paper_id}`}
                      className="font-medium hover:text-primary transition-colors line-clamp-2"
                    >
                      {assessment.paper_title}
                    </Link>
                    <p className="text-sm text-muted-foreground">
                      {sourceLabel(assessment.paper_source || "")} •{" "}
                      {assessment.paper_external_id}
                    </p>
                  </td>
                  <td className="px-4 py-4">
                    <div className="text-xs space-y-1">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Pathogen:</span>
                        <span>{assessment.pathogen_score.toFixed(0)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">GoF:</span>
                        <span>{assessment.gof_score.toFixed(0)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Contain:</span>
                        <span>{assessment.containment_score.toFixed(0)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Dual-use:</span>
                        <span>{assessment.dual_use_score.toFixed(0)}</span>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-4 text-sm text-muted-foreground">
                    {formatDate(assessment.assessed_at)}
                  </td>
                  <td className="px-4 py-4">
                    {assessment.flagged ? (
                      <span className="inline-flex items-center rounded-full bg-destructive/20 px-2 py-1 text-xs font-medium text-destructive">
                        Flagged
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
                        Normal
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data?.assessments.length === 0 && (
            <div className="p-8 text-center text-muted-foreground">
              No assessments found
            </div>
          )}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="inline-flex items-center gap-1 rounded-lg bg-muted px-3 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-muted/80 transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="inline-flex items-center gap-1 rounded-lg bg-muted px-3 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-muted/80 transition-colors"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

