"use client";

import { useState } from "react";
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
} from "lucide-react";

interface ScanResult {
  success: boolean;
  message: string;
  count?: number;
}

export default function ScanPage() {
  const queryClient = useQueryClient();
  const [results, setResults] = useState<ScanResult[]>([]);

  const addResult = (result: ScanResult) => {
    setResults((prev) => [...prev, result]);
  };

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

  const scanAll = useMutation({
    mutationFn: () => scanApi.all(30),
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
      addResult({ success: false, message: `Full scan failed: ${error}` });
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

  const isAnyLoading =
    scanArxiv.isPending ||
    scanBiorxiv.isPending ||
    scanPubmed.isPending ||
    scanAll.isPending ||
    assessPapers.isPending ||
    researchFacility.isPending;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Scan & Assess</h1>
        <p className="text-muted-foreground">
          Fetch new papers and run biosecurity assessments
        </p>
      </div>

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

        {/* Scan All */}
        <button
          onClick={() => scanAll.mutate()}
          disabled={isAnyLoading}
          className="rounded-xl border border-primary/50 bg-primary/10 p-6 text-left hover:bg-primary/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="flex items-center gap-4">
            <div className="rounded-lg bg-primary/20 p-3">
              {scanAll.isPending ? (
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              ) : (
                <RefreshCw className="h-6 w-6 text-primary" />
              )}
            </div>
            <div>
              <h3 className="font-medium text-primary">Scan All Sources</h3>
              <p className="text-sm text-muted-foreground">
                Fetch from all paper sources
              </p>
            </div>
          </div>
        </button>

        {/* Assess Papers */}
        <button
          onClick={() => assessPapers.mutate()}
          disabled={isAnyLoading}
          className="rounded-xl border border-accent/50 bg-accent/10 p-6 text-left hover:bg-accent/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="flex items-center gap-4">
            <div className="rounded-lg bg-accent/20 p-3">
              {assessPapers.isPending ? (
                <Loader2 className="h-6 w-6 animate-spin text-accent" />
              ) : (
                <Brain className="h-6 w-6 text-accent" />
              )}
            </div>
            <div>
              <h3 className="font-medium text-accent">Assess Papers</h3>
              <p className="text-sm text-muted-foreground">
                Run AI biosecurity analysis
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

