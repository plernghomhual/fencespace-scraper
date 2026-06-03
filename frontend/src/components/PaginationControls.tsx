import { ArrowLeft, ArrowRight } from "lucide-react";

import { ButtonLink } from "@/components/ui/button";
import type { Pagination, SearchParams } from "@/lib/types";

function hrefWithOffset(pathname: string, params: SearchParams, offset: number): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    const first = Array.isArray(value) ? value[0] : value;
    if (first && key !== "offset") {
      search.set(key, first);
    }
  }
  search.set("offset", String(offset));
  const query = search.toString();
  return query ? `${pathname}?${query}` : pathname;
}

export function PaginationControls({
  pathname,
  params,
  pagination,
}: {
  pathname: string;
  params: SearchParams;
  pagination: Pagination;
}) {
  const previousOffset = Math.max(0, pagination.offset - pagination.limit);
  const nextOffset = pagination.offset + pagination.limit;
  const hasPrevious = pagination.offset > 0;
  const hasNext = pagination.count >= pagination.limit;

  return (
    <nav aria-label="Pagination" className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
      <span>
        Showing {pagination.count} rows from offset {pagination.offset}
      </span>
      <div className="flex gap-2">
        <ButtonLink
          aria-disabled={!hasPrevious}
          className={!hasPrevious ? "pointer-events-none opacity-50" : undefined}
          href={hrefWithOffset(pathname, params, previousOffset)}
          variant="outline"
        >
          <ArrowLeft aria-hidden="true" data-icon="inline-start" />
          Previous
        </ButtonLink>
        <ButtonLink
          aria-disabled={!hasNext}
          className={!hasNext ? "pointer-events-none opacity-50" : undefined}
          href={hrefWithOffset(pathname, params, nextOffset)}
          variant="outline"
        >
          Next
          <ArrowRight aria-hidden="true" data-icon="inline-end" />
        </ButtonLink>
      </div>
    </nav>
  );
}
