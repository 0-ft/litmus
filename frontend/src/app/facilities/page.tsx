"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { facilitiesApi, Facility } from "@/lib/api";
import { ChevronLeft, ChevronRight, Building2, Shield, MapPin } from "lucide-react";

export default function FacilitiesPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["facilities", page],
    queryFn: () => facilitiesApi.list(page, pageSize),
  });

  const { data: searchResults } = useQuery({
    queryKey: ["facility-search", search],
    queryFn: () => facilitiesApi.search(search),
    enabled: search.length >= 2,
  });

  const displayFacilities = search.length >= 2 ? searchResults : data?.facilities;
  const totalPages = search.length >= 2 ? 1 : Math.ceil((data?.total || 0) / pageSize);

  const getBslColor = (level: number | null) => {
    switch (level) {
      case 4:
        return "bg-grade-f/20 text-grade-f border-grade-f/50";
      case 3:
        return "bg-grade-d/20 text-grade-d border-grade-d/50";
      case 2:
        return "bg-grade-c/20 text-grade-c border-grade-c/50";
      case 1:
        return "bg-grade-a/20 text-grade-a border-grade-a/50";
      default:
        return "bg-muted text-muted-foreground border-border";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Facilities</h1>
          <p className="text-muted-foreground">
            {data?.total || 0} facilities in database
          </p>
        </div>
        {/* Search */}
        <div className="relative">
          <input
            type="text"
            placeholder="Search facilities..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-lg border border-border bg-card px-4 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>
      </div>

      {/* Facilities Grid */}
      {isLoading ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
          Loading facilities...
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {displayFacilities?.map((facility: Facility) => {
            const aliases = facility.aliases
              ? JSON.parse(facility.aliases)
              : [];

            return (
              <div
                key={facility.id}
                className="rounded-xl border border-border bg-card p-6 card-hover"
              >
                <div className="flex items-start gap-4">
                  <div className="rounded-lg bg-muted p-3">
                    <Building2 className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium truncate">{facility.name}</h3>
                    {aliases.length > 0 && (
                      <p className="text-sm text-muted-foreground truncate">
                        {aliases.join(", ")}
                      </p>
                    )}
                  </div>
                </div>

                <div className="mt-4 space-y-2">
                  {/* BSL Level */}
                  <div className="flex items-center gap-2">
                    <Shield className="h-4 w-4 text-muted-foreground" />
                    {facility.bsl_level ? (
                      <span
                        className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium ${getBslColor(
                          facility.bsl_level
                        )}`}
                      >
                        BSL-{facility.bsl_level}
                      </span>
                    ) : (
                      <span className="text-sm text-muted-foreground">
                        BSL Unknown
                      </span>
                    )}
                  </div>

                  {/* Location */}
                  {(facility.city || facility.country) && (
                    <div className="flex items-center gap-2">
                      <MapPin className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm text-muted-foreground">
                        {[facility.city, facility.country]
                          .filter(Boolean)
                          .join(", ")}
                      </span>
                    </div>
                  )}
                </div>

                {/* Verified badge */}
                <div className="mt-4 flex items-center justify-between">
                  {facility.verified ? (
                    <span className="inline-flex items-center rounded-full bg-grade-a/20 px-2 py-1 text-xs font-medium text-grade-a">
                      ✓ Verified
                    </span>
                  ) : (
                    <span className="inline-flex items-center rounded-full bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
                      Unverified
                    </span>
                  )}
                  {facility.source_url && (
                    <a
                      href={facility.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-primary hover:underline"
                    >
                      Source
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {displayFacilities?.length === 0 && (
        <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
          {search ? "No facilities found matching your search" : "No facilities in database"}
        </div>
      )}

      {/* Pagination */}
      {!search && totalPages > 1 && (
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

