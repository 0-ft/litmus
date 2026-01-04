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
  // Debug/trace fields
  input_prompt: string | null;
  raw_output: string | null;
  // Joined fields
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

export interface FetchPaperResponse {
  success: boolean;
  message: string;
  paper_id?: number;
  title?: string;
  source?: string;
  already_exists: boolean;
}

// Reference Assessment types
export interface FacilityInfo {
  name: string;
  bsl_level: string;
}

export interface ReferenceAssessment {
  id: number;
  paper_id: number;
  created_by: string | null;
  overall_score: number;
  pathogen_score: number;
  gof_score: number;
  containment_score: number;
  dual_use_score: number;
  pathogens_identified: string[] | null;
  research_facilities: FacilityInfo[] | null;
  stated_bsl: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  paper_title?: string;
  paper_source?: string;
  paper_external_id?: string;
}

export interface ReferenceAssessmentCreate {
  paper_id: number;
  created_by?: string;
  overall_score: number;
  pathogen_score: number;
  gof_score: number;
  containment_score: number;
  dual_use_score: number;
  pathogens_identified?: string[];
  research_facilities?: FacilityInfo[];
  stated_bsl?: string;
  notes?: string;
}

export interface ScoreComparison {
  ai_score: number;
  reference_score: number;
  difference: number;
  absolute_error: number;
}

export interface ComparisonResult {
  paper_id: number;
  paper_title: string;
  ai_assessment_id: number;
  reference_assessment_id: number;
  overall: ScoreComparison;
  pathogen: ScoreComparison;
  gof: ScoreComparison;
  containment: ScoreComparison;
  dual_use: ScoreComparison;
  pathogens_ai: string[];
  pathogens_reference: string[];
  pathogens_matched: string[];
  pathogens_missed: string[];
  pathogens_extra: string[];
  pathogen_precision: number;
  pathogen_recall: number;
  pathogen_f1: number;
  facilities_ai: FacilityInfo[];
  facilities_reference: FacilityInfo[];
  facilities_matched: string[];
  facilities_missed: string[];
  facilities_extra: string[];
  facility_precision: number;
  facility_recall: number;
  facility_f1: number;
  bsl_ai: string | null;
  bsl_reference: string | null;
  bsl_match: boolean;
}

export interface AggregateMetrics {
  num_papers: number;
  mean_absolute_error: Record<string, number>;
  mean_signed_error: Record<string, number>;
  score_correlation: Record<string, number>;
  avg_pathogen_precision: number;
  avg_pathogen_recall: number;
  avg_pathogen_f1: number;
  avg_facility_precision: number;
  avg_facility_recall: number;
  avg_facility_f1: number;
  bsl_accuracy: number;
}

export interface FullComparisonResponse {
  comparisons: ComparisonResult[];
  aggregate: AggregateMetrics;
}

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
  
  assess: (limit = 500) =>
    fetchApi<{ message: string; papers_assessed: number; flagged: number }>(`/api/scan/assess?limit=${limit}`, { method: "POST" }),
  
  researchFacility: (facilityName: string) =>
    fetchApi<{ message: string; facility_name: string; found: boolean; facility_id?: number; bsl_level?: number; confidence?: string }>(
      `/api/scan/research-facility?facility_name=${encodeURIComponent(facilityName)}`,
      { method: "POST" }
    ),
  
  fetchPaper: (url: string) =>
    fetchApi<FetchPaperResponse>(`/api/scan/fetch-paper`, {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  
  assessPaper: (paperId: number, force = false) =>
    fetchApi<{
      success: boolean;
      message: string;
      paper_id: number;
      risk_grade?: string;
      overall_score?: number;
      flagged: boolean;
      flag_reason?: string;
      concerns_summary?: string;
      pathogens?: string[];
      already_assessed: boolean;
    }>(`/api/scan/assess-paper/${paperId}?force=${force}`, { method: "POST" }),
  
  clearAssessments: () =>
    fetchApi<{ message: string; assessments_deleted: number }>(`/api/scan/assessments`, {
      method: "DELETE",
    }),
};

// Reference Assessments API
export const referenceApi = {
  list: () =>
    fetchApi<ReferenceAssessment[]>(`/api/reference/`),
  
  forPaper: (paperId: number) =>
    fetchApi<ReferenceAssessment>(`/api/reference/paper/${paperId}`),
  
  create: (data: ReferenceAssessmentCreate) =>
    fetchApi<ReferenceAssessment>(`/api/reference/`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  
  update: (paperId: number, data: Partial<ReferenceAssessmentCreate>) =>
    fetchApi<ReferenceAssessment>(`/api/reference/paper/${paperId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  
  delete: (paperId: number) =>
    fetchApi<{ message: string }>(`/api/reference/paper/${paperId}`, {
      method: "DELETE",
    }),
  
  compare: () =>
    fetchApi<FullComparisonResponse>(`/api/reference/compare`),
  
  compareOne: (paperId: number) =>
    fetchApi<ComparisonResult>(`/api/reference/compare/paper/${paperId}`),
};

