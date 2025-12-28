import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | null): string {
  if (!date) return "Unknown";
  return new Date(date).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function parseAuthors(authorsJson: string): string[] {
  try {
    const authors = JSON.parse(authorsJson);
    return Array.isArray(authors) ? authors : [authorsJson];
  } catch {
    return [authorsJson];
  }
}

export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - 3) + "...";
}

export function getGradeColor(grade: string): string {
  const colors: Record<string, string> = {
    A: "text-grade-a",
    B: "text-grade-b",
    C: "text-grade-c",
    D: "text-grade-d",
    F: "text-grade-f",
  };
  return colors[grade] || "text-muted-foreground";
}

export function getGradeBgColor(grade: string): string {
  const colors: Record<string, string> = {
    A: "bg-grade-a/20 border-grade-a/50",
    B: "bg-grade-b/20 border-grade-b/50",
    C: "bg-grade-c/20 border-grade-c/50",
    D: "bg-grade-d/20 border-grade-d/50",
    F: "bg-grade-f/20 border-grade-f/50",
  };
  return colors[grade] || "bg-muted border-border";
}

export function getScoreColor(score: number): string {
  if (score < 20) return "text-grade-a";
  if (score < 40) return "text-grade-b";
  if (score < 60) return "text-grade-c";
  if (score < 80) return "text-grade-d";
  return "text-grade-f";
}

export function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    arxiv: "arXiv",
    biorxiv: "bioRxiv",
    medrxiv: "medRxiv",
    pubmed: "PubMed",
  };
  return labels[source] || source;
}

