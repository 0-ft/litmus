"use client";

import Link from "next/link";
import { Paper, Assessment } from "@/lib/api";
import { RiskBadge } from "./RiskBadge";
import { cn, formatDate, parseAuthors, truncate, sourceLabel } from "@/lib/utils";
import { ExternalLink, FileText } from "lucide-react";

interface PaperTableProps {
  papers: Paper[];
  assessments?: Map<number, Assessment>;
  showAssessment?: boolean;
}

export function PaperTable({ papers, assessments, showAssessment = false }: PaperTableProps) {
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border bg-muted/50">
            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Paper
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Source
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Date
            </th>
            {showAssessment && (
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Risk
              </th>
            )}
            <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Status
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {papers.map((paper) => {
            const assessment = assessments?.get(paper.id);
            const authors = parseAuthors(paper.authors);

            return (
              <tr key={paper.id} className="hover:bg-muted/30 transition-colors">
                <td className="px-4 py-4">
                  <div className="flex items-start gap-3">
                    <div className="mt-1 rounded-lg bg-muted p-2">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <Link
                        href={`/papers/${paper.id}`}
                        className="font-medium text-foreground hover:text-primary transition-colors line-clamp-2"
                      >
                        {paper.title}
                      </Link>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {truncate(authors.slice(0, 3).join(", "), 60)}
                        {authors.length > 3 && ` +${authors.length - 3} more`}
                      </p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-4">
                  <span className="inline-flex items-center rounded-md bg-muted px-2 py-1 text-xs font-medium">
                    {sourceLabel(paper.source)}
                  </span>
                </td>
                <td className="px-4 py-4 text-sm text-muted-foreground">
                  {formatDate(paper.published_date)}
                </td>
                {showAssessment && (
                  <td className="px-4 py-4">
                    {assessment ? (
                      <RiskBadge
                        grade={assessment.risk_grade}
                        score={assessment.overall_score}
                        showScore
                      />
                    ) : (
                      <span className="text-sm text-muted-foreground">—</span>
                    )}
                  </td>
                )}
                <td className="px-4 py-4">
                  <div className="flex items-center gap-2">
                    {paper.processed ? (
                      <span className="inline-flex items-center rounded-full bg-grade-a/20 px-2 py-1 text-xs font-medium text-grade-a">
                        Assessed
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
                        Pending
                      </span>
                    )}
                    {paper.url && (
                      <a
                        href={paper.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {papers.length === 0 && (
        <div className="p-8 text-center text-muted-foreground">
          No papers found
        </div>
      )}
    </div>
  );
}

