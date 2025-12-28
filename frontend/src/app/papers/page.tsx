"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { papersApi, assessmentsApi } from "@/lib/api";
import { PaperTable } from "@/components/PaperTable";
import { ChevronLeft, ChevronRight } from "lucide-react";

export default function PapersPage() {
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data: papersData, isLoading: papersLoading } = useQuery({
    queryKey: ["papers", page],
    queryFn: () => papersApi.list(page, pageSize),
  });

  const { data: assessmentsData } = useQuery({
    queryKey: ["assessments-all"],
    queryFn: () => assessmentsApi.list(1, 1000),
  });

  // Build assessment map
  const assessmentMap = new Map(
    assessmentsData?.assessments.map((a) => [a.paper_id, a]) || []
  );

  const totalPages = Math.ceil((papersData?.total || 0) / pageSize);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Papers</h1>
          <p className="text-muted-foreground">
            {papersData?.total || 0} papers in database
          </p>
        </div>
      </div>

      {/* Table */}
      {papersLoading ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
          Loading papers...
        </div>
      ) : (
        <PaperTable
          papers={papersData?.papers || []}
          assessments={assessmentMap}
          showAssessment
        />
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

