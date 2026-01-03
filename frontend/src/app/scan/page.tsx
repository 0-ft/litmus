"use client";

import { useState, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { scanApi } from "@/lib/api";
import {
  RefreshCw,
  FileText,
  Search,
  Brain,
  CheckCircle,
  AlertCircle,
  Loader2,
  Circle,
  XCircle,
  Link,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ScanResult {
  success: boolean;
  message: string;
  count?: number;
}

interface SourceProgress {
  status: "pending" | "scanning" | "complete" | "error";
  papersFound: number;
  sampleTitles: string[];
  error?: string;
}

interface ScanProgress {
  isScanning: boolean;
  sources: {
    arxiv: SourceProgress;
    biorxiv: SourceProgress;
    medrxiv: SourceProgress;
    pubmed: SourceProgress;
  };
  totalPapers: number;
  currentMessage: string;
}

interface AssessedPaper {
  paper_id: number;
  title: string;
  risk_grade: string;
  overall_score: number;
  flagged: boolean;
  flag_reason?: string;
  concerns_summary?: string;
  pathogens: string[];
}

interface AssessProgress {
  isAssessing: boolean;
  currentPaper: string;
  progress: string;
  assessed: number;
  flagged: number;
  totalPapers: number;
  currentMessage: string;
  completedPapers: AssessedPaper[];
}

const initialSourceProgress: SourceProgress = {
  status: "pending",
  papersFound: 0,
  sampleTitles: [],
};

const initialProgress: ScanProgress = {
  isScanning: false,
  sources: {
    arxiv: { ...initialSourceProgress },
    biorxiv: { ...initialSourceProgress },
    medrxiv: { ...initialSourceProgress },
    pubmed: { ...initialSourceProgress },
  },
  totalPapers: 0,
  currentMessage: "",
};

const initialAssessProgress: AssessProgress = {
  isAssessing: false,
  currentPaper: "",
  progress: "",
  assessed: 0,
  flagged: 0,
  totalPapers: 0,
  currentMessage: "",
  completedPapers: [],
};

export default function ScanPage() {
  const queryClient = useQueryClient();
  const [results, setResults] = useState<ScanResult[]>([]);
  const [scanProgress, setScanProgress] = useState<ScanProgress>(initialProgress);
  const [assessProgress, setAssessProgress] = useState<AssessProgress>(initialAssessProgress);

  const addResult = (result: ScanResult) => {
    setResults((prev) => [...prev, result]);
  };

  const startStreamingAssess = useCallback(async () => {
    // Reset progress
    setAssessProgress({
      ...initialAssessProgress,
      isAssessing: true,
      currentMessage: "Connecting...",
    });

    try {
      const response = await fetch(`${API_BASE}/api/scan/assess/stream?limit=10`);
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("Failed to get stream reader");
      }

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              
              setAssessProgress((prev) => {
                const newProgress = { ...prev };

                if (data.message) {
                  newProgress.currentMessage = data.message;
                }

                if (data.total_papers !== undefined) {
                  newProgress.totalPapers = data.total_papers;
                }

                // Paper starting assessment
                if (data.title && data.progress && !data.risk_grade) {
                  newProgress.currentPaper = data.title;
                  newProgress.progress = data.progress;
                }

                // Paper completed assessment
                if (data.risk_grade !== undefined) {
                  newProgress.completedPapers = [
                    ...prev.completedPapers,
                    {
                      paper_id: data.paper_id,
                      title: data.title,
                      risk_grade: data.risk_grade,
                      overall_score: data.overall_score,
                      flagged: data.flagged,
                      flag_reason: data.flag_reason,
                      concerns_summary: data.concerns_summary,
                      pathogens: data.pathogens || [],
                    },
                  ];
                  newProgress.assessed = data.assessed_so_far || prev.assessed + 1;
                  newProgress.flagged = data.flagged_so_far || prev.flagged;
                  newProgress.progress = data.progress;
                  newProgress.currentPaper = "";
                }

                // Paper error
                if (data.error && data.paper_id) {
                  newProgress.currentPaper = "";
                }

                // Complete event
                if (data.assessed !== undefined && data.flagged !== undefined && !data.paper_id) {
                  newProgress.isAssessing = false;
                  newProgress.assessed = data.assessed;
                  newProgress.flagged = data.flagged;
                }

                return newProgress;
              });
            } catch (e) {
              // Ignore parse errors
            }
          }
        }
      }

      // Assessment complete
      setAssessProgress((prev) => ({
        ...prev,
        isAssessing: false,
      }));
      
      queryClient.invalidateQueries({ queryKey: ["assessments"] });
      queryClient.invalidateQueries({ queryKey: ["assessment-stats"] });
      queryClient.invalidateQueries({ queryKey: ["flagged"] });
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      
      addResult({
        success: true,
        message: `Assessment complete!`,
      });

    } catch (error) {
      setAssessProgress((prev) => ({
        ...prev,
        isAssessing: false,
        currentMessage: `Error: ${error}`,
      }));
      addResult({
        success: false,
        message: `Assessment failed: ${error}`,
      });
    }
  }, [queryClient]);

  const startStreamingScan = useCallback(async () => {
    // Reset progress
    setScanProgress({
      ...initialProgress,
      isScanning: true,
      currentMessage: "Connecting...",
    });

    try {
      const response = await fetch(`${API_BASE}/api/scan/all/stream?max_results_per_source=30`);
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("Failed to get stream reader");
      }

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            const eventType = line.slice(7);
            continue;
          }
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              
              setScanProgress((prev) => {
                const newProgress = { ...prev };

                if (data.message) {
                  newProgress.currentMessage = data.message;
                }

                if (data.source) {
                  const source = data.source as keyof typeof prev.sources;
                  
                  if (line.includes("source_start")) {
                    newProgress.sources = {
                      ...prev.sources,
                      [source]: {
                        ...prev.sources[source],
                        status: "scanning",
                      },
                    };
                  } else if (line.includes("source_complete") || data.papers_fetched !== undefined) {
                    newProgress.sources = {
                      ...prev.sources,
                      [source]: {
                        status: "complete",
                        papersFound: data.papers_fetched || 0,
                        sampleTitles: data.sample_titles || [],
                      },
                    };
                    newProgress.totalPapers = Object.values(newProgress.sources)
                      .reduce((sum, s) => sum + s.papersFound, 0);
                  } else if (data.error) {
                    newProgress.sources = {
                      ...prev.sources,
                      [source]: {
                        ...prev.sources[source],
                        status: "error",
                        error: data.error,
                      },
                    };
                  }
                }

                if (data.total_papers !== undefined) {
                  newProgress.totalPapers = data.total_papers;
                  newProgress.isScanning = false;
                  newProgress.currentMessage = data.message || "Scan complete!";
                }

                return newProgress;
              });
            } catch (e) {
              // Ignore parse errors
            }
          }
        }
      }

      // Scan complete
      setScanProgress((prev) => ({
        ...prev,
        isScanning: false,
      }));
      
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      queryClient.invalidateQueries({ queryKey: ["paper-stats"] });
      
      addResult({
        success: true,
        message: `Scan complete! Fetched papers from all sources.`,
      });

    } catch (error) {
      setScanProgress((prev) => ({
        ...prev,
        isScanning: false,
        currentMessage: `Error: ${error}`,
      }));
      addResult({
        success: false,
        message: `Scan failed: ${error}`,
      });
    }
  }, [queryClient]);

  const scanArxiv = useMutation({
    mutationFn: () => scanApi.arxiv(50),
    onSuccess: (data) => {
      addResult({
        success: true,
        message: data.message,
        count: data.papers_fetched,
      });
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      queryClient.invalidateQueries({ queryKey: ["paper-stats"] });
    },
    onError: (error) => {
      addResult({ success: false, message: `arXiv scan failed: ${error}` });
    },
  });

  const scanBiorxiv = useMutation({
    mutationFn: () => scanApi.biorxiv(50, 7),
    onSuccess: (data) => {
      addResult({
        success: true,
        message: data.message,
        count: data.papers_fetched,
      });
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      queryClient.invalidateQueries({ queryKey: ["paper-stats"] });
    },
    onError: (error) => {
      addResult({ success: false, message: `bioRxiv scan failed: ${error}` });
    },
  });

  const scanPubmed = useMutation({
    mutationFn: () => scanApi.pubmed(50, 7),
    onSuccess: (data) => {
      addResult({
        success: true,
        message: data.message,
        count: data.papers_fetched,
      });
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      queryClient.invalidateQueries({ queryKey: ["paper-stats"] });
    },
    onError: (error) => {
      addResult({ success: false, message: `PubMed scan failed: ${error}` });
    },
  });

  const assessPapers = useMutation({
    mutationFn: () => scanApi.assess(10),
    onSuccess: (data) => {
      addResult({
        success: true,
        message: data.message,
        count: data.papers_assessed,
      });
      queryClient.invalidateQueries({ queryKey: ["assessments"] });
      queryClient.invalidateQueries({ queryKey: ["assessment-stats"] });
      queryClient.invalidateQueries({ queryKey: ["flagged"] });
    },
    onError: (error) => {
      addResult({ success: false, message: `Assessment failed: ${error}` });
    },
  });

  const [facilitySearch, setFacilitySearch] = useState("");
  const [paperUrl, setPaperUrl] = useState("");
  
  const researchFacility = useMutation({
    mutationFn: (name: string) => scanApi.researchFacility(name),
    onSuccess: (data) => {
      addResult({
        success: data.found,
        message: data.message + (data.bsl_level ? ` (BSL-${data.bsl_level})` : ""),
      });
      queryClient.invalidateQueries({ queryKey: ["facilities"] });
      queryClient.invalidateQueries({ queryKey: ["facility-stats"] });
    },
    onError: (error) => {
      addResult({
        success: false,
        message: `Facility research failed: ${error}`,
      });
    },
  });

  const fetchPaper = useMutation({
    mutationFn: (url: string) => scanApi.fetchPaper(url),
    onSuccess: (data) => {
      const statusMsg = data.already_exists ? " (already in database)" : "";
      addResult({
        success: data.success,
        message: `${data.message}${statusMsg}${data.title ? `: "${data.title}"` : ""}`,
      });
      setPaperUrl("");
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      queryClient.invalidateQueries({ queryKey: ["paper-stats"] });
    },
    onError: (error) => {
      addResult({
        success: false,
        message: `Failed to fetch paper: ${error}`,
      });
    },
  });

  const isAnyLoading =
    scanArxiv.isPending ||
    scanBiorxiv.isPending ||
    scanPubmed.isPending ||
    scanProgress.isScanning ||
    assessProgress.isAssessing ||
    assessPapers.isPending ||
    researchFacility.isPending ||
    fetchPaper.isPending;

  const SourceStatusIcon = ({ status }: { status: SourceProgress["status"] }) => {
    switch (status) {
      case "pending":
        return <Circle className="h-4 w-4 text-muted-foreground" />;
      case "scanning":
        return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
      case "complete":
        return <CheckCircle className="h-4 w-4 text-grade-a" />;
      case "error":
        return <XCircle className="h-4 w-4 text-destructive" />;
    }
  };

  const sourceLabels: Record<string, string> = {
    arxiv: "arXiv",
    biorxiv: "bioRxiv",
    medrxiv: "medRxiv",
    pubmed: "PubMed",
  };

  const getGradeColor = (grade: string) => {
    switch (grade) {
      case "A": return "text-grade-a bg-grade-a/10 border-grade-a/30";
      case "B": return "text-grade-b bg-grade-b/10 border-grade-b/30";
      case "C": return "text-grade-c bg-grade-c/10 border-grade-c/30";
      case "D": return "text-grade-d bg-grade-d/10 border-grade-d/30";
      case "F": return "text-grade-f bg-grade-f/10 border-grade-f/30";
      default: return "text-muted-foreground bg-muted border-border";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Scan & Assess</h1>
        <p className="text-muted-foreground">
          Fetch new papers and run biosecurity assessments
        </p>
      </div>

      {/* Streaming Scan Progress */}
      {(scanProgress.isScanning || scanProgress.totalPapers > 0) && (
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {scanProgress.isScanning ? (
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
              ) : (
                <CheckCircle className="h-5 w-5 text-grade-a" />
              )}
              <span className="font-medium">
                {scanProgress.isScanning ? "Scanning Sources..." : "Scan Complete"}
              </span>
            </div>
            <span className="text-sm text-muted-foreground">
              {scanProgress.totalPapers} papers found
            </span>
          </div>

          <div className="text-sm text-muted-foreground">
            {scanProgress.currentMessage}
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {(Object.entries(scanProgress.sources) as [string, SourceProgress][]).map(
              ([source, progress]) => (
                <div
                  key={source}
                  className={`rounded-lg border p-3 transition-all ${
                    progress.status === "scanning"
                      ? "border-primary/50 bg-primary/10"
                      : progress.status === "complete"
                      ? "border-grade-a/30 bg-grade-a/5"
                      : progress.status === "error"
                      ? "border-destructive/30 bg-destructive/5"
                      : "border-border bg-card"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <SourceStatusIcon status={progress.status} />
                      <span className="font-medium text-sm">
                        {sourceLabels[source]}
                      </span>
                    </div>
                    {progress.status === "complete" && (
                      <span className="text-xs text-muted-foreground">
                        {progress.papersFound} papers
                      </span>
                    )}
                  </div>
                  {progress.sampleTitles.length > 0 && (
                    <div className="space-y-1">
                      {progress.sampleTitles.slice(0, 2).map((title, i) => (
                        <p
                          key={i}
                          className="text-xs text-muted-foreground truncate"
                          title={title}
                        >
                          • {title}
                        </p>
                      ))}
                    </div>
                  )}
                  {progress.error && (
                    <p className="text-xs text-destructive mt-1">
                      {progress.error}
                    </p>
                  )}
                </div>
              )
            )}
          </div>

          {!scanProgress.isScanning && (
            <button
              onClick={() => setScanProgress(initialProgress)}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Dismiss
            </button>
          )}
        </div>
      )}

      {/* Streaming Assessment Progress */}
      {(assessProgress.isAssessing || assessProgress.completedPapers.length > 0) && (
        <div className="rounded-xl border border-accent/30 bg-accent/5 p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {assessProgress.isAssessing ? (
                <Loader2 className="h-5 w-5 animate-spin text-accent" />
              ) : (
                <CheckCircle className="h-5 w-5 text-grade-a" />
              )}
              <span className="font-medium">
                {assessProgress.isAssessing ? "Running AI Assessment..." : "Assessment Complete"}
              </span>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <span className="text-muted-foreground">
                {assessProgress.assessed} assessed
              </span>
              {assessProgress.flagged > 0 && (
                <span className="text-grade-f font-medium">
                  {assessProgress.flagged} flagged
                </span>
              )}
            </div>
          </div>

          <div className="text-sm text-muted-foreground">
            {assessProgress.currentMessage}
          </div>

          {/* Current paper being assessed */}
          {assessProgress.isAssessing && assessProgress.currentPaper && (
            <div className="rounded-lg border border-accent/20 bg-accent/10 p-3">
              <div className="flex items-center gap-2 mb-1">
                <Loader2 className="h-4 w-4 animate-spin text-accent" />
                <span className="text-sm font-medium text-accent">
                  Analyzing ({assessProgress.progress})
                </span>
              </div>
              <p className="text-sm text-muted-foreground truncate">
                {assessProgress.currentPaper}
              </p>
            </div>
          )}

          {/* Completed papers list */}
          {assessProgress.completedPapers.length > 0 && (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {assessProgress.completedPapers.slice().reverse().map((paper) => (
                <div
                  key={paper.paper_id}
                  className={`rounded-lg border p-3 transition-all ${
                    paper.flagged
                      ? "border-grade-f/30 bg-grade-f/5"
                      : "border-border bg-card"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate" title={paper.title}>
                        {paper.title}
                      </p>
                      {paper.concerns_summary && (
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                          {paper.concerns_summary}
                        </p>
                      )}
                      {paper.pathogens.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {paper.pathogens.slice(0, 3).map((pathogen, i) => (
                            <span
                              key={i}
                              className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
                            >
                              {pathogen}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span
                        className={`text-xs font-bold px-2 py-1 rounded border ${getGradeColor(
                          paper.risk_grade
                        )}`}
                      >
                        {paper.risk_grade}
                      </span>
                      {paper.flagged && (
                        <AlertCircle className="h-4 w-4 text-grade-f" />
                      )}
                    </div>
                  </div>
                  {paper.flagged && paper.flag_reason && (
                    <p className="text-xs text-grade-f mt-2">
                      ⚠️ {paper.flag_reason}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {!assessProgress.isAssessing && (
            <button
              onClick={() => setAssessProgress(initialAssessProgress)}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Dismiss
            </button>
          )}
        </div>
      )}

      {/* Actions Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Scan arXiv */}
        <button
          onClick={() => scanArxiv.mutate()}
          disabled={isAnyLoading}
          className="rounded-xl border border-border bg-card p-6 text-left hover:border-primary/50 hover:bg-card/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="flex items-center gap-4">
            <div className="rounded-lg bg-muted p-3">
              {scanArxiv.isPending ? (
                <Loader2 className="h-6 w-6 animate-spin" />
              ) : (
                <FileText className="h-6 w-6 text-muted-foreground" />
              )}
            </div>
            <div>
              <h3 className="font-medium">Scan arXiv</h3>
              <p className="text-sm text-muted-foreground">
                Fetch biology papers from arXiv
              </p>
            </div>
          </div>
        </button>

        {/* Scan bioRxiv */}
        <button
          onClick={() => scanBiorxiv.mutate()}
          disabled={isAnyLoading}
          className="rounded-xl border border-border bg-card p-6 text-left hover:border-primary/50 hover:bg-card/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="flex items-center gap-4">
            <div className="rounded-lg bg-muted p-3">
              {scanBiorxiv.isPending ? (
                <Loader2 className="h-6 w-6 animate-spin" />
              ) : (
                <FileText className="h-6 w-6 text-muted-foreground" />
              )}
            </div>
            <div>
              <h3 className="font-medium">Scan bioRxiv</h3>
              <p className="text-sm text-muted-foreground">
                Fetch from bioRxiv & medRxiv
              </p>
            </div>
          </div>
        </button>

        {/* Scan PubMed */}
        <button
          onClick={() => scanPubmed.mutate()}
          disabled={isAnyLoading}
          className="rounded-xl border border-border bg-card p-6 text-left hover:border-primary/50 hover:bg-card/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="flex items-center gap-4">
            <div className="rounded-lg bg-muted p-3">
              {scanPubmed.isPending ? (
                <Loader2 className="h-6 w-6 animate-spin" />
              ) : (
                <FileText className="h-6 w-6 text-muted-foreground" />
              )}
            </div>
            <div>
              <h3 className="font-medium">Scan PubMed</h3>
              <p className="text-sm text-muted-foreground">
                Fetch from PubMed database
              </p>
            </div>
          </div>
        </button>

        {/* Scan All - Now uses streaming */}
        <button
          onClick={startStreamingScan}
          disabled={isAnyLoading}
          className="rounded-xl border border-primary/50 bg-primary/10 p-6 text-left hover:bg-primary/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="flex items-center gap-4">
            <div className="rounded-lg bg-primary/20 p-3">
              {scanProgress.isScanning ? (
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              ) : (
                <RefreshCw className="h-6 w-6 text-primary" />
              )}
            </div>
            <div>
              <h3 className="font-medium text-primary">Scan All Sources</h3>
              <p className="text-sm text-muted-foreground">
                Fetch from all sources with live progress
              </p>
            </div>
          </div>
        </button>

        {/* Assess Papers - Now uses streaming */}
        <button
          onClick={startStreamingAssess}
          disabled={isAnyLoading}
          className="rounded-xl border border-accent/50 bg-accent/10 p-6 text-left hover:bg-accent/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="flex items-center gap-4">
            <div className="rounded-lg bg-accent/20 p-3">
              {assessProgress.isAssessing ? (
                <Loader2 className="h-6 w-6 animate-spin text-accent" />
              ) : (
                <Brain className="h-6 w-6 text-accent" />
              )}
            </div>
            <div>
              <h3 className="font-medium text-accent">Assess Papers</h3>
              <p className="text-sm text-muted-foreground">
                Run AI biosecurity analysis with live progress
              </p>
            </div>
          </div>
        </button>

        {/* Research Facility */}
        <div className="rounded-xl border border-border bg-card p-6">
          <div className="flex items-center gap-4 mb-4">
            <div className="rounded-lg bg-muted p-3">
              {researchFacility.isPending ? (
                <Loader2 className="h-6 w-6 animate-spin" />
              ) : (
                <Search className="h-6 w-6 text-muted-foreground" />
              )}
            </div>
            <div>
              <h3 className="font-medium">Research Facility</h3>
              <p className="text-sm text-muted-foreground">
                Search for BSL level info
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Facility name..."
              value={facilitySearch}
              onChange={(e) => setFacilitySearch(e.target.value)}
              className="flex-1 rounded-lg border border-border bg-muted px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            <button
              onClick={() => {
                if (facilitySearch.trim()) {
                  researchFacility.mutate(facilitySearch.trim());
                }
              }}
              disabled={isAnyLoading || !facilitySearch.trim()}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              Search
            </button>
          </div>
        </div>
      </div>

      {/* Fetch Paper by URL */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex items-center gap-4 mb-4">
          <div className="rounded-lg bg-muted p-3">
            {fetchPaper.isPending ? (
              <Loader2 className="h-6 w-6 animate-spin" />
            ) : (
              <Link className="h-6 w-6 text-muted-foreground" />
            )}
          </div>
          <div>
            <h3 className="font-medium">Fetch Paper by URL</h3>
            <p className="text-sm text-muted-foreground">
              Import a specific paper from arXiv, bioRxiv, medRxiv, or PubMed
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="https://arxiv.org/abs/2401.12345 or PMID:12345678..."
            value={paperUrl}
            onChange={(e) => setPaperUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && paperUrl.trim() && !isAnyLoading) {
                fetchPaper.mutate(paperUrl.trim());
              }
            }}
            className="flex-1 rounded-lg border border-border bg-muted px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
          <button
            onClick={() => {
              if (paperUrl.trim()) {
                fetchPaper.mutate(paperUrl.trim());
              }
            }}
            disabled={isAnyLoading || !paperUrl.trim()}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            Fetch
          </button>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Supported: arXiv URLs, bioRxiv/medRxiv URLs, PubMed URLs, or just a PMID
        </p>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="rounded-xl border border-border bg-card">
          <div className="border-b border-border px-6 py-4">
            <div className="flex items-center justify-between">
              <h2 className="font-medium">Results</h2>
              <button
                onClick={() => setResults([])}
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                Clear
              </button>
            </div>
          </div>
          <div className="divide-y divide-border">
            {results.map((result, idx) => (
              <div key={idx} className="flex items-center gap-3 px-6 py-3">
                {result.success ? (
                  <CheckCircle className="h-5 w-5 text-grade-a" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-destructive" />
                )}
                <span
                  className={
                    result.success ? "text-foreground" : "text-destructive"
                  }
                >
                  {result.message}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Instructions */}
      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="font-medium mb-4">How to Use</h2>
        <ol className="space-y-2 text-sm text-muted-foreground list-decimal list-inside">
          <li>
            <strong>Scan Sources</strong> - Fetch recent papers from arXiv,
            bioRxiv, or PubMed
          </li>
          <li>
            <strong>Assess Papers</strong> - Run AI analysis on unprocessed
            papers (requires Anthropic API key)
          </li>
          <li>
            <strong>Research Facilities</strong> - Look up BSL levels for
            specific facilities (requires Tavily API key)
          </li>
          <li>
            <strong>Review Flagged</strong> - Check the Flagged page for papers
            requiring human review
          </li>
        </ol>
        <div className="mt-4 p-3 rounded-lg bg-muted/50">
          <p className="text-xs">
            <strong>Note:</strong> Facilities are automatically researched during
            assessment if TAVILY_API_KEY is configured. All facility data requires
            human verification.
          </p>
        </div>
      </div>
    </div>
  );
}
