const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Paper {
  id: number;
  source: string;
  external_id: string;
  title: string;
  authors: string;
  abstract: string | null;
  url: string | null;
  published_date: string | null;
  fetched_at: string;
  processed: boolean;
  categories: string | null;
}

export interface Assessment {
  id: number;
  paper_id: number;
  risk_grade: string;
  overall_score: number;
  pathogen_score: number;
  gof_score: number;
  containment_score: number;
  dual_use_score: number;
  rationale: string;
  concerns_summary: string | null;
  pathogens_identified: string | null;
  flagged: boolean;
  flag_reason: string | null;
  assessed_at: string;
  model_version: string | null;
  paper_title?: string;
  paper_source?: string;
  paper_external_id?: string;
}

export interface Facility {
  id: number;
  name: string;
  aliases: string | null;
  country: string | null;
  city: string | null;
  bsl_level: number | null;
  verified: boolean;
  source_url: string | null;
}

export interface PaperListResponse {
  papers: Paper[];
  total: number;
  page: number;
  page_size: number;
}

export interface AssessmentListResponse {
  assessments: Assessment[];
  total: number;
  page: number;
  page_size: number;
}

export interface FacilityListResponse {
  facilities: Facility[];
  total: number;
  page: number;
  page_size: number;
}

export interface Stats {
  total: number;
  processed?: number;
  unprocessed?: number;
  flagged?: number;
  verified?: number;
  by_source?: Record<string, number>;
  by_grade?: Record<string, number>;
  by_bsl_level?: Record<string, number>;
  by_country?: Record<string, number>;
  average_scores?: {
    overall: number;
    pathogen: number;
    gof: number;
    containment: number;
    dual_use: number;
  };
}

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

// Papers API
export const papersApi = {
  list: (page = 1, pageSize = 20) =>
    fetchApi<PaperListResponse>(`/api/papers/?page=${page}&page_size=${pageSize}`),
  
  get: (id: number) =>
    fetchApi<Paper>(`/api/papers/${id}`),
  
  stats: () =>
    fetchApi<Stats>(`/api/papers/stats/summary`),
};

// Assessments API
export const assessmentsApi = {
  list: (page = 1, pageSize = 20, filters?: { risk_grade?: string; flagged?: boolean; min_score?: number }) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (filters?.risk_grade) params.append("risk_grade", filters.risk_grade);
    if (filters?.flagged !== undefined) params.append("flagged", String(filters.flagged));
    if (filters?.min_score !== undefined) params.append("min_score", String(filters.min_score));
    return fetchApi<AssessmentListResponse>(`/api/assessments/?${params}`);
  },
  
  get: (id: number) =>
    fetchApi<Assessment>(`/api/assessments/${id}`),
  
  flagged: () =>
    fetchApi<Assessment[]>(`/api/assessments/flagged`),
  
  forPaper: (paperId: number) =>
    fetchApi<Assessment[]>(`/api/assessments/paper/${paperId}`),
  
  stats: () =>
    fetchApi<Stats>(`/api/assessments/stats/summary`),
};

// Facilities API
export const facilitiesApi = {
  list: (page = 1, pageSize = 20) =>
    fetchApi<FacilityListResponse>(`/api/facilities/?page=${page}&page_size=${pageSize}`),
  
  get: (id: number) =>
    fetchApi<Facility>(`/api/facilities/${id}`),
  
  search: (name: string) =>
    fetchApi<Facility[]>(`/api/facilities/search/name?name=${encodeURIComponent(name)}`),
  
  stats: () =>
    fetchApi<Stats>(`/api/facilities/stats/summary`),
};

// Scan API
export const scanApi = {
  arxiv: (maxResults = 100) =>
    fetchApi<{ message: string; papers_fetched: number }>(`/api/scan/arxiv?max_results=${maxResults}`, { method: "POST" }),
  
  biorxiv: (maxResults = 100, daysBack = 7) =>
    fetchApi<{ message: string; papers_fetched: number }>(`/api/scan/biorxiv?max_results=${maxResults}&days_back=${daysBack}`, { method: "POST" }),
  
  pubmed: (maxResults = 100, daysBack = 7) =>
    fetchApi<{ message: string; papers_fetched: number }>(`/api/scan/pubmed?max_results=${maxResults}&days_back=${daysBack}`, { method: "POST" }),
  
  all: (maxResultsPerSource = 50) =>
    fetchApi<{ message: string; papers_fetched: number }>(`/api/scan/all?max_results_per_source=${maxResultsPerSource}`, { method: "POST" }),
  
  assess: (limit = 10) =>
    fetchApi<{ message: string; papers_assessed: number; flagged: number }>(`/api/scan/assess?limit=${limit}`, { method: "POST" }),
  
  researchFacility: (facilityName: string) =>
    fetchApi<{ message: string; facility_name: string; found: boolean; facility_id?: number; bsl_level?: number; confidence?: string }>(
      `/api/scan/research-facility?facility_name=${encodeURIComponent(facilityName)}`,
      { method: "POST" }
    ),
};

