"use client";

import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, papersApi } from "@/lib/api";
import { AssessmentDetail } from "@/components/AssessmentDetail";
import { formatDate, parseAuthors, sourceLabel } from "@/lib/utils";
import Link from "next/link";
import { ArrowLeft, ExternalLink } from "lucide-react";

export default function AssessmentDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const assessmentId = parseInt(params.id);

  const { data: assessment, isLoading } = useQuery({
    queryKey: ["assessment", assessmentId],
    queryFn: () => assessmentsApi.get(assessmentId),
  });

  const { data: paper } = useQuery({
    queryKey: ["paper", assessment?.paper_id],
    queryFn: () => papersApi.get(assessment!.paper_id),
    enabled: !!assessment?.paper_id,
  });

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
        Loading assessment...
      </div>
    );
  }

  if (!assessment) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
        Assessment not found
      </div>
    );
  }

  const authors = paper ? parseAuthors(paper.authors) : [];

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/assessments"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Assessments
      </Link>

      {/* Paper Info */}
      {paper && (
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className="inline-flex items-center rounded-md bg-muted px-2 py-1 text-xs font-medium">
                  {sourceLabel(paper.source)}
                </span>
                <span className="text-sm text-muted-foreground">
                  {paper.external_id}
                </span>
              </div>
              <Link
                href={`/papers/${paper.id}`}
                className="text-xl font-bold hover:text-primary transition-colors"
              >
                {paper.title}
              </Link>
              <p className="mt-2 text-muted-foreground">
                {authors.join(", ")}
              </p>
            </div>
            {paper.url && (
              <a
                href={paper.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-lg bg-muted px-4 py-2 text-sm font-medium hover:bg-muted/80 transition-colors"
              >
                <ExternalLink className="h-4 w-4" />
                View Source
              </a>
            )}
          </div>
          <div className="mt-4 text-sm text-muted-foreground">
            Published: {formatDate(paper.published_date)}
          </div>
        </div>
      )}

      {/* Assessment Detail */}
      <div className="rounded-xl border border-border bg-card p-6">
        <AssessmentDetail assessment={assessment} />
      </div>
    </div>
  );
}

