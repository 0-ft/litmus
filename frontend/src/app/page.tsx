"use client";

import { useQuery } from "@tanstack/react-query";
import { papersApi, assessmentsApi, facilitiesApi, Assessment } from "@/lib/api";
import { StatsCard } from "@/components/StatsCard";
import { RiskBadge } from "@/components/RiskBadge";
import { formatDate, sourceLabel } from "@/lib/utils";
import Link from "next/link";
import {
  FileText,
  ShieldAlert,
  AlertTriangle,
  Building2,
  TrendingUp,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const GRADE_COLORS = {
  A: "#22c55e",
  B: "#84cc16",
  C: "#eab308",
  D: "#f97316",
  F: "#ef4444",
};

export default function DashboardPage() {
  const { data: paperStats } = useQuery({
    queryKey: ["paper-stats"],
    queryFn: papersApi.stats,
  });

  const { data: assessmentStats } = useQuery({
    queryKey: ["assessment-stats"],
    queryFn: assessmentsApi.stats,
  });

  const { data: facilityStats } = useQuery({
    queryKey: ["facility-stats"],
    queryFn: facilitiesApi.stats,
  });

  const { data: flaggedAssessments } = useQuery({
    queryKey: ["flagged"],
    queryFn: assessmentsApi.flagged,
  });

  // Prepare chart data
  const gradeData = assessmentStats?.by_grade
    ? Object.entries(assessmentStats.by_grade).map(([grade, count]) => ({
        grade,
        count,
        fill: GRADE_COLORS[grade as keyof typeof GRADE_COLORS],
      }))
    : [];

  const sourceData = paperStats?.by_source
    ? Object.entries(paperStats.by_source).map(([source, count]) => ({
        source: sourceLabel(source),
        count,
      }))
    : [];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Biosecurity risk monitoring overview
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          title="Total Papers"
          value={paperStats?.total || 0}
          subtitle={`${paperStats?.unprocessed || 0} pending assessment`}
          icon={FileText}
        />
        <StatsCard
          title="Assessments"
          value={assessmentStats?.total || 0}
          subtitle={
            assessmentStats?.average_scores
              ? `Avg score: ${assessmentStats.average_scores.overall.toFixed(1)}`
              : undefined
          }
          icon={ShieldAlert}
        />
        <StatsCard
          title="Flagged Papers"
          value={assessmentStats?.flagged || 0}
          subtitle="Require review"
          icon={AlertTriangle}
          variant={
            (assessmentStats?.flagged || 0) > 0 ? "danger" : "default"
          }
        />
        <StatsCard
          title="Facilities"
          value={facilityStats?.total || 0}
          subtitle={`${facilityStats?.verified || 0} verified`}
          icon={Building2}
        />
      </div>

      {/* Charts Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Risk Distribution */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h2 className="font-medium mb-4">Risk Grade Distribution</h2>
          {gradeData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={gradeData}>
                  <XAxis dataKey="grade" stroke="#71717a" />
                  <YAxis stroke="#71717a" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#111116",
                      border: "1px solid #27272a",
                      borderRadius: "8px",
                    }}
                  />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {gradeData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              No assessment data yet
            </div>
          )}
        </div>

        {/* Papers by Source */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h2 className="font-medium mb-4">Papers by Source</h2>
          {sourceData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={sourceData}
                    dataKey="count"
                    nameKey="source"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ source, count }) => `${source}: ${count}`}
                  >
                    {sourceData.map((_, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={`hsl(${index * 90}, 70%, 50%)`}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#111116",
                      border: "1px solid #27272a",
                      borderRadius: "8px",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              No paper data yet
            </div>
          )}
        </div>
      </div>

      {/* Flagged Papers */}
      <div className="rounded-xl border border-border bg-card">
        <div className="border-b border-border px-6 py-4">
          <div className="flex items-center justify-between">
            <h2 className="font-medium">Recently Flagged Papers</h2>
            <Link
              href="/flagged"
              className="text-sm text-primary hover:underline"
            >
              View all →
            </Link>
          </div>
        </div>
        <div className="divide-y divide-border">
          {flaggedAssessments && flaggedAssessments.length > 0 ? (
            flaggedAssessments.slice(0, 5).map((assessment: Assessment) => (
              <Link
                key={assessment.id}
                href={`/assessments/${assessment.id}`}
                className="flex items-center gap-4 px-6 py-4 hover:bg-muted/30 transition-colors"
              >
                <RiskBadge grade={assessment.risk_grade} />
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">
                    {assessment.paper_title}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {assessment.flag_reason || "High risk score"}
                  </p>
                </div>
                <div className="text-right text-sm text-muted-foreground">
                  <p>Score: {assessment.overall_score.toFixed(1)}</p>
                  <p>{formatDate(assessment.assessed_at)}</p>
                </div>
              </Link>
            ))
          ) : (
            <div className="px-6 py-8 text-center text-muted-foreground">
              No flagged papers yet
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="font-medium mb-4">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/scan"
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <TrendingUp className="h-4 w-4" />
            Scan for New Papers
          </Link>
          <Link
            href="/papers"
            className="inline-flex items-center gap-2 rounded-lg bg-muted px-4 py-2 text-sm font-medium hover:bg-muted/80 transition-colors"
          >
            <FileText className="h-4 w-4" />
            View All Papers
          </Link>
          <Link
            href="/facilities"
            className="inline-flex items-center gap-2 rounded-lg bg-muted px-4 py-2 text-sm font-medium hover:bg-muted/80 transition-colors"
          >
            <Building2 className="h-4 w-4" />
            Manage Facilities
          </Link>
        </div>
      </div>
    </div>
  );
}

