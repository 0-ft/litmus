"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { papersApi, assessmentsApi, queueApi, QueueItem } from "@/lib/api";
import { AssessmentDetail } from "@/components/AssessmentDetail";
import { formatDate, parseAuthors, sourceLabel } from "@/lib/utils";
import Link from "next/link";
import { ArrowLeft, ExternalLink, ListOrdered, Loader2, RefreshCw, Clock, CheckCircle } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function PaperDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const paperId = parseInt(params.id);
  const queryClient = useQueryClient();
  const [queueMessage, setQueueMessage] = useState<string | null>(null);
  const [isInQueue, setIsInQueue] = useState(false);

  const { data: paper, isLoading: paperLoading } = useQuery({
    queryKey: ["paper", paperId],
    queryFn: () => papersApi.get(paperId),
  });

  const { data: assessments, refetch: refetchAssessments } = useQuery({
    queryKey: ["paper-assessments", paperId],
    queryFn: () => assessmentsApi.forPaper(paperId),
  });

  // Check if paper is in queue
  const { data: queueItems } = useQuery({
    queryKey: ["queue-items-for-paper", paperId],
    queryFn: async () => {
      const items = await queueApi.items(undefined, 100);
      return items.filter(item => item.paper_id === paperId);
    },
    refetchInterval: isInQueue ? 2000 : false,
  });

  // Update isInQueue state
  useEffect(() => {
    const pendingOrProcessing = queueItems?.some(
      item => item.status === "pending" || item.status === "processing"
    );
    setIsInQueue(!!pendingOrProcessing);
    
    // If assessment completed, refresh assessments
    const completed = queueItems?.some(
      item => item.status === "completed"
    );
    if (completed) {
      refetchAssessments();
      queryClient.invalidateQueries({ queryKey: ["paper", paperId] });
    }
  }, [queueItems, refetchAssessments, queryClient, paperId]);

  // Add to queue mutation
  const addToQueueMutation = useMutation({
    mutationFn: () => queueApi.addPaper(paperId, 1), // Priority 1 = high priority
    onSuccess: (data) => {
      if (data.already_queued > 0) {
        setQueueMessage("Paper is already in the assessment queue");
      } else {
        setQueueMessage("Paper added to assessment queue");
        setIsInQueue(true);
      }
      queryClient.invalidateQueries({ queryKey: ["queue-items-for-paper", paperId] });
    },
    onError: (error) => {
      setQueueMessage(`Error: ${error}`);
    },
  });

  const currentQueueItem = queueItems?.find(
    item => item.status === "pending" || item.status === "processing"
  );

  const latestAssessment = assessments?.[0];
  const authors = paper ? parseAuthors(paper.authors) : [];
  const categories = paper?.categories ? JSON.parse(paper.categories) : [];

  if (paperLoading) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
        Loading paper...
      </div>
    );
  }

  if (!paper) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
        Paper not found
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/papers"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Papers
      </Link>

      {/* Paper Info */}
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
            <h1 className="text-xl font-bold">{paper.title}</h1>
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

        {/* Meta */}
        <div className="mt-4 flex flex-wrap gap-4 text-sm text-muted-foreground">
          <span>Published: {formatDate(paper.published_date)}</span>
          <span>Fetched: {formatDate(paper.fetched_at)}</span>
          {paper.processed && (
            <span className="text-grade-a">✓ Assessed</span>
          )}
        </div>

        {/* Categories */}
        {categories.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {categories.map((cat: string, idx: number) => (
              <span
                key={idx}
                className="rounded-full bg-muted px-3 py-1 text-xs"
              >
                {cat}
              </span>
            ))}
          </div>
        )}

        {/* Abstract */}
        {paper.abstract && (
          <div className="mt-6">
            <h2 className="font-medium mb-2">Abstract</h2>
            <p className="text-muted-foreground whitespace-pre-wrap">
              {paper.abstract}
            </p>
          </div>
        )}
      </div>

      {/* Queue Status */}
      {currentQueueItem && (
        <div className="rounded-xl border border-accent/30 bg-accent/5 p-4">
          <div className="flex items-center gap-3">
            {currentQueueItem.status === "processing" ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin text-accent" />
                <span className="text-sm font-medium text-accent">
                  Assessment in progress...
                </span>
              </>
            ) : (
              <>
                <Clock className="h-5 w-5 text-accent" />
                <span className="text-sm font-medium text-accent">
                  Queued for assessment
                </span>
              </>
            )}
          </div>
        </div>
      )}

      {/* Assessment */}
      {latestAssessment ? (
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-medium">Biosecurity Assessment</h2>
            <button
              onClick={() => addToQueueMutation.mutate()}
              disabled={addToQueueMutation.isPending || isInQueue}
              className="inline-flex items-center gap-2 rounded-lg bg-muted px-3 py-1.5 text-sm font-medium hover:bg-muted/80 transition-colors disabled:opacity-50"
            >
              {addToQueueMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : isInQueue ? (
                <Clock className="h-4 w-4" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              {isInQueue ? "In Queue" : "Re-assess"}
            </button>
          </div>
          {queueMessage && (
            <div className="mb-4 p-3 rounded-lg bg-muted text-sm">
              {queueMessage}
            </div>
          )}
          <AssessmentDetail assessment={latestAssessment} />
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="text-center space-y-4">
            <p className="text-muted-foreground">
              This paper has not been assessed yet.
            </p>
            <button
              onClick={() => addToQueueMutation.mutate()}
              disabled={addToQueueMutation.isPending || isInQueue}
              className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-foreground hover:bg-accent/80 transition-colors disabled:opacity-50"
            >
              {addToQueueMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Adding to queue...
                </>
              ) : isInQueue ? (
                <>
                  <Clock className="h-4 w-4" />
                  In Queue
                </>
              ) : (
                <>
                  <ListOrdered className="h-4 w-4" />
                  Queue Assessment
                </>
              )}
            </button>
            {queueMessage && (
              <p className="text-sm text-muted-foreground">{queueMessage}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

