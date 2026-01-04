"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { referenceApi, papersApi, Paper, ReferenceAssessment, FullComparisonResponse, FacilityInfo } from "@/lib/api";
import Link from "next/link";
import {
  FlaskConical,
  Plus,
  TrendingUp,
  Target,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  MinusCircle,
  FileText,
} from "lucide-react";

function ScoreComparisonBar({
  label,
  aiScore,
  refScore,
  maxScore = 10,
}: {
  label: string;
  aiScore: number;
  refScore: number;
  maxScore?: number;
}) {
  const aiPercent = (aiScore / maxScore) * 100;
  const refPercent = (refScore / maxScore) * 100;
  const diff = aiScore - refScore;
  const diffColor = Math.abs(diff) < 1 ? "text-green-500" : Math.abs(diff) < 2 ? "text-yellow-500" : "text-red-500";

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className={diffColor}>
          {diff > 0 ? "+" : ""}{diff.toFixed(1)}
        </span>
      </div>
      <div className="relative h-3 bg-muted rounded-full overflow-hidden">
        {/* Reference score marker */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-blue-500 z-10"
          style={{ left: `${refPercent}%` }}
          title={`Reference: ${refScore.toFixed(1)}`}
        />
        {/* AI score bar */}
        <div
          className="absolute left-0 top-0 h-full bg-orange-500/70 rounded-full"
          style={{ width: `${aiPercent}%` }}
          title={`AI: ${aiScore.toFixed(1)}`}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>AI: {aiScore.toFixed(1)}</span>
        <span>Ref: {refScore.toFixed(1)}</span>
      </div>
    </div>
  );
}

function MetricCard({ label, value, suffix = "", color = "text-foreground" }: { label: string; value: number | string; suffix?: string; color?: string }) {
  return (
    <div className="rounded-lg bg-muted/50 p-3">
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div className={`text-xl font-bold ${color}`}>
        {typeof value === "number" ? value.toFixed(2) : value}{suffix}
      </div>
    </div>
  );
}

function ComparisonRow({ comparison }: { comparison: FullComparisonResponse["comparisons"][0] }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors text-left"
      >
        <div className="flex-1">
          <Link 
            href={`/papers/${comparison.paper_id}`}
            className="font-medium hover:text-primary transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            {comparison.paper_title}
          </Link>
          <div className="flex gap-4 mt-1 text-sm text-muted-foreground">
            <span>Overall: AI {comparison.overall.ai_score.toFixed(1)} vs Ref {comparison.overall.reference_score.toFixed(1)}</span>
            <span className={comparison.bsl_match ? "text-green-500" : "text-red-500"}>
              BSL: {comparison.bsl_match ? "✓ Match" : "✗ Mismatch"}
            </span>
          </div>
        </div>
        {expanded ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
      </button>

      {expanded && (
        <div className="border-t border-border p-4 bg-muted/30">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Score Comparisons */}
            <div className="space-y-4">
              <h4 className="font-medium">Score Comparison</h4>
              <ScoreComparisonBar label="Overall" aiScore={comparison.overall.ai_score} refScore={comparison.overall.reference_score} />
              <ScoreComparisonBar label="Pathogen" aiScore={comparison.pathogen.ai_score} refScore={comparison.pathogen.reference_score} />
              <ScoreComparisonBar label="GoF" aiScore={comparison.gof.ai_score} refScore={comparison.gof.reference_score} />
              <ScoreComparisonBar label="Containment" aiScore={comparison.containment.ai_score} refScore={comparison.containment.reference_score} />
              <ScoreComparisonBar label="Dual Use" aiScore={comparison.dual_use.ai_score} refScore={comparison.dual_use.reference_score} />
            </div>

            {/* Pathogen & Facility Comparison */}
            <div className="space-y-4">
              {/* BSL */}
              <div>
                <h4 className="font-medium mb-2">BSL Level</h4>
                <div className="flex gap-4 text-sm">
                  <span>AI: {comparison.bsl_ai || "Unknown"}</span>
                  <span>Reference: {comparison.bsl_reference || "Unknown"}</span>
                  {comparison.bsl_match ? (
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-500" />
                  )}
                </div>
              </div>

              {/* Pathogens */}
              <div>
                <h4 className="font-medium mb-2">Pathogens</h4>
                <div className="text-xs text-muted-foreground mb-2">
                  P: {(comparison.pathogen_precision * 100).toFixed(0)}% | R: {(comparison.pathogen_recall * 100).toFixed(0)}% | F1: {(comparison.pathogen_f1 * 100).toFixed(0)}%
                </div>
                <div className="flex flex-wrap gap-1">
                  {comparison.pathogens_matched.map((p, i) => (
                    <span key={i} className="px-2 py-0.5 text-xs rounded bg-green-500/20 text-green-700 dark:text-green-400">
                      ✓ {p}
                    </span>
                  ))}
                  {comparison.pathogens_missed.map((p, i) => (
                    <span key={i} className="px-2 py-0.5 text-xs rounded bg-red-500/20 text-red-700 dark:text-red-400">
                      − {p}
                    </span>
                  ))}
                  {comparison.pathogens_extra.map((p, i) => (
                    <span key={i} className="px-2 py-0.5 text-xs rounded bg-yellow-500/20 text-yellow-700 dark:text-yellow-400">
                      + {p}
                    </span>
                  ))}
                </div>
              </div>

              {/* Facilities */}
              <div>
                <h4 className="font-medium mb-2">Facilities</h4>
                <div className="text-xs text-muted-foreground mb-2">
                  P: {(comparison.facility_precision * 100).toFixed(0)}% | R: {(comparison.facility_recall * 100).toFixed(0)}% | F1: {(comparison.facility_f1 * 100).toFixed(0)}%
                </div>
                <div className="flex flex-wrap gap-1">
                  {comparison.facilities_matched.map((f, i) => (
                    <span key={i} className="px-2 py-0.5 text-xs rounded bg-green-500/20 text-green-700 dark:text-green-400">
                      ✓ {f}
                    </span>
                  ))}
                  {comparison.facilities_missed.map((f, i) => (
                    <span key={i} className="px-2 py-0.5 text-xs rounded bg-red-500/20 text-red-700 dark:text-red-400">
                      − {f}
                    </span>
                  ))}
                  {comparison.facilities_extra.map((f, i) => (
                    <span key={i} className="px-2 py-0.5 text-xs rounded bg-yellow-500/20 text-yellow-700 dark:text-yellow-400">
                      + {f}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AggregateMetricsPanel({ aggregate }: { aggregate: FullComparisonResponse["aggregate"] }) {
  return (
    <div className="rounded-xl border border-border bg-card p-6">
      <h3 className="font-medium mb-4 flex items-center gap-2">
        <TrendingUp className="h-5 w-5" />
        Aggregate Metrics ({aggregate.num_papers} papers)
      </h3>
      
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {/* Score MAE */}
        <MetricCard 
          label="Overall MAE" 
          value={aggregate.mean_absolute_error.overall} 
          color={aggregate.mean_absolute_error.overall < 1 ? "text-green-500" : aggregate.mean_absolute_error.overall < 2 ? "text-yellow-500" : "text-red-500"}
        />
        <MetricCard 
          label="Pathogen MAE" 
          value={aggregate.mean_absolute_error.pathogen}
        />
        <MetricCard 
          label="Containment MAE" 
          value={aggregate.mean_absolute_error.containment}
        />
        
        {/* Entity Detection */}
        <MetricCard 
          label="Pathogen F1" 
          value={aggregate.avg_pathogen_f1 * 100}
          suffix="%"
          color={aggregate.avg_pathogen_f1 > 0.8 ? "text-green-500" : aggregate.avg_pathogen_f1 > 0.6 ? "text-yellow-500" : "text-red-500"}
        />
        <MetricCard 
          label="Facility F1" 
          value={aggregate.avg_facility_f1 * 100}
          suffix="%"
        />
        <MetricCard 
          label="BSL Accuracy" 
          value={aggregate.bsl_accuracy * 100}
          suffix="%"
          color={aggregate.bsl_accuracy > 0.8 ? "text-green-500" : aggregate.bsl_accuracy > 0.5 ? "text-yellow-500" : "text-red-500"}
        />
      </div>

      {/* Detailed Score Metrics */}
      <div className="mt-6 pt-4 border-t border-border">
        <h4 className="text-sm font-medium mb-3">Score Correlations</h4>
        <div className="grid grid-cols-5 gap-2 text-sm">
          {["overall", "pathogen", "gof", "containment", "dual_use"].map((cat) => (
            <div key={cat} className="text-center">
              <div className="text-muted-foreground text-xs capitalize">{cat.replace("_", " ")}</div>
              <div className={`font-medium ${aggregate.score_correlation[cat] > 0.7 ? "text-green-500" : aggregate.score_correlation[cat] > 0.4 ? "text-yellow-500" : "text-red-500"}`}>
                {aggregate.score_correlation[cat].toFixed(2)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ReferenceAssessmentForm({ 
  paperId, 
  existingRef,
  onSave 
}: { 
  paperId: number; 
  existingRef?: ReferenceAssessment;
  onSave: () => void;
}) {
  const [formData, setFormData] = useState({
    overall_score: existingRef?.overall_score ?? 0,
    pathogen_score: existingRef?.pathogen_score ?? 0,
    gof_score: existingRef?.gof_score ?? 0,
    containment_score: existingRef?.containment_score ?? 0,
    dual_use_score: existingRef?.dual_use_score ?? 0,
    pathogens: existingRef?.pathogens_identified?.join(", ") ?? "",
    facilities: existingRef?.research_facilities?.map(f => `${f.name} (${f.bsl_level})`).join(", ") ?? "",
    stated_bsl: existingRef?.stated_bsl ?? "",
    notes: existingRef?.notes ?? "",
    created_by: existingRef?.created_by ?? "",
  });

  const queryClient = useQueryClient();

  const saveMutation = useMutation({
    mutationFn: async () => {
      const pathogens = formData.pathogens.split(",").map(s => s.trim()).filter(Boolean);
      const facilities: FacilityInfo[] = formData.facilities.split(",").map(s => {
        const match = s.trim().match(/^(.+?)\s*\((.+?)\)$/);
        if (match) return { name: match[1].trim(), bsl_level: match[2].trim() };
        return { name: s.trim(), bsl_level: "Unknown" };
      }).filter(f => f.name);

      const data = {
        paper_id: paperId,
        overall_score: formData.overall_score,
        pathogen_score: formData.pathogen_score,
        gof_score: formData.gof_score,
        containment_score: formData.containment_score,
        dual_use_score: formData.dual_use_score,
        pathogens_identified: pathogens.length > 0 ? pathogens : undefined,
        research_facilities: facilities.length > 0 ? facilities : undefined,
        stated_bsl: formData.stated_bsl || undefined,
        notes: formData.notes || undefined,
        created_by: formData.created_by || undefined,
      };

      if (existingRef) {
        return referenceApi.update(paperId, data);
      } else {
        return referenceApi.create(data);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["references"] });
      queryClient.invalidateQueries({ queryKey: ["reference", paperId] });
      queryClient.invalidateQueries({ queryKey: ["comparison"] });
      onSave();
    },
  });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-5 gap-4">
        {[
          { key: "overall_score", label: "Overall" },
          { key: "pathogen_score", label: "Pathogen" },
          { key: "gof_score", label: "GoF" },
          { key: "containment_score", label: "Containment" },
          { key: "dual_use_score", label: "Dual Use" },
        ].map(({ key, label }) => (
          <div key={key}>
            <label className="text-xs text-muted-foreground">{label} (0-10)</label>
            <input
              type="number"
              min="0"
              max="10"
              step="0.5"
              value={formData[key as keyof typeof formData]}
              onChange={(e) => setFormData({ ...formData, [key]: parseFloat(e.target.value) || 0 })}
              className="w-full mt-1 px-3 py-2 rounded-lg bg-muted border border-border text-sm"
            />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-xs text-muted-foreground">Pathogens (comma-separated)</label>
          <input
            type="text"
            value={formData.pathogens}
            onChange={(e) => setFormData({ ...formData, pathogens: e.target.value })}
            placeholder="SARS-CoV-2, Influenza A"
            className="w-full mt-1 px-3 py-2 rounded-lg bg-muted border border-border text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground">Stated BSL</label>
          <input
            type="text"
            value={formData.stated_bsl}
            onChange={(e) => setFormData({ ...formData, stated_bsl: e.target.value })}
            placeholder="BSL-2, BSL-3, Unknown"
            className="w-full mt-1 px-3 py-2 rounded-lg bg-muted border border-border text-sm"
          />
        </div>
      </div>

      <div>
        <label className="text-xs text-muted-foreground">Facilities (format: "Name (BSL-X)", comma-separated)</label>
        <input
          type="text"
          value={formData.facilities}
          onChange={(e) => setFormData({ ...formData, facilities: e.target.value })}
          placeholder="Wuhan Institute of Virology (BSL-4), CDC Atlanta (BSL-3)"
          className="w-full mt-1 px-3 py-2 rounded-lg bg-muted border border-border text-sm"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-xs text-muted-foreground">Created By</label>
          <input
            type="text"
            value={formData.created_by}
            onChange={(e) => setFormData({ ...formData, created_by: e.target.value })}
            placeholder="Your name"
            className="w-full mt-1 px-3 py-2 rounded-lg bg-muted border border-border text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground">Notes</label>
          <input
            type="text"
            value={formData.notes}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
            placeholder="Any additional notes"
            className="w-full mt-1 px-3 py-2 rounded-lg bg-muted border border-border text-sm"
          />
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          {saveMutation.isPending ? "Saving..." : existingRef ? "Update" : "Create"}
        </button>
      </div>
    </div>
  );
}

function CreateReferenceModal({ 
  isOpen, 
  onClose 
}: { 
  isOpen: boolean; 
  onClose: () => void;
}) {
  const [selectedPaperId, setSelectedPaperId] = useState<number | null>(null);

  const { data: papers } = useQuery({
    queryKey: ["papers-for-reference"],
    queryFn: () => papersApi.list(1, 100),
    enabled: isOpen,
  });

  const { data: existingRef } = useQuery({
    queryKey: ["reference", selectedPaperId],
    queryFn: () => selectedPaperId ? referenceApi.forPaper(selectedPaperId) : null,
    enabled: !!selectedPaperId,
    retry: false,
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-2xl rounded-xl bg-card border border-border p-6 m-4 max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold mb-4">Create Reference Assessment</h2>

        {!selectedPaperId ? (
          <div>
            <label className="text-sm text-muted-foreground">Select a paper:</label>
            <select
              value=""
              onChange={(e) => setSelectedPaperId(parseInt(e.target.value))}
              className="w-full mt-2 px-3 py-2 rounded-lg bg-muted border border-border"
            >
              <option value="">Choose a paper...</option>
              {papers?.papers.map((paper) => (
                <option key={paper.id} value={paper.id}>
                  [{paper.id}] {paper.title.substring(0, 80)}...
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div>
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-muted-foreground">Paper ID: {selectedPaperId}</span>
              <button
                onClick={() => setSelectedPaperId(null)}
                className="text-sm text-primary hover:underline"
              >
                Change paper
              </button>
            </div>
            <ReferenceAssessmentForm
              paperId={selectedPaperId}
              existingRef={existingRef || undefined}
              onSave={onClose}
            />
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-muted text-sm font-medium hover:bg-muted/80"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

export default function EvaluationPage() {
  const [showCreateModal, setShowCreateModal] = useState(false);

  const { data: references, isLoading: refsLoading } = useQuery({
    queryKey: ["references"],
    queryFn: referenceApi.list,
  });

  const { data: comparison, isLoading: compLoading } = useQuery({
    queryKey: ["comparison"],
    queryFn: referenceApi.compare,
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <FlaskConical className="h-7 w-7" />
            Pipeline Evaluation
          </h1>
          <p className="text-muted-foreground mt-1">
            Compare AI assessments against human gold standards
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          Add Reference
        </button>
      </div>

      {/* Aggregate Metrics */}
      {comparison && comparison.aggregate.num_papers > 0 && (
        <AggregateMetricsPanel aggregate={comparison.aggregate} />
      )}

      {/* Reference List */}
      <div className="rounded-xl border border-border bg-card">
        <div className="p-4 border-b border-border">
          <h3 className="font-medium flex items-center gap-2">
            <Target className="h-5 w-5" />
            Reference Assessments ({references?.length || 0})
          </h3>
        </div>

        {refsLoading ? (
          <div className="p-8 text-center text-muted-foreground">Loading...</div>
        ) : references?.length === 0 ? (
          <div className="p-8 text-center">
            <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">No reference assessments yet.</p>
            <p className="text-sm text-muted-foreground mt-1">
              Create gold standard assessments to compare against AI pipeline outputs.
            </p>
          </div>
        ) : (
          <div className="p-4 space-y-3">
            {comparison?.comparisons.map((comp) => (
              <ComparisonRow key={comp.paper_id} comparison={comp} />
            ))}
            {/* References without AI assessment */}
            {references?.filter(ref => !comparison?.comparisons.find(c => c.paper_id === ref.paper_id)).map(ref => (
              <div key={ref.id} className="border border-border rounded-lg p-4">
                <Link 
                  href={`/papers/${ref.paper_id}`}
                  className="font-medium hover:text-primary transition-colors"
                >
                  {ref.paper_title}
                </Link>
                <div className="text-sm text-muted-foreground mt-1 flex items-center gap-2">
                  <MinusCircle className="h-4 w-4" />
                  No AI assessment yet - run assessment to compare
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Modal */}
      <CreateReferenceModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
      />
    </div>
  );
}

