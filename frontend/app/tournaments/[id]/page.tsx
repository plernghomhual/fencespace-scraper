import { TournamentResultsTable } from "@/components/DataTables";
import { PageHeader } from "@/components/PageHeader";
import { PaginationControls } from "@/components/PaginationControls";
import { EmptyState, ErrorState } from "@/components/StatePanels";
import { ButtonLink } from "@/components/ui/button";
import { getTournamentResults, parsePaginationParams } from "@/lib/api";
import type { SearchParams } from "@/lib/types";
import { resolveRouteParams, resolveSearchParams } from "@/lib/utils";

export default async function TournamentDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams?: Promise<SearchParams>;
}) {
  const [{ id }, paramsObj] = await Promise.all([resolveRouteParams(params), resolveSearchParams(searchParams)]);
  const queryParams = paramsObj || {};
  const query = parsePaginationParams(queryParams);
  const result = await getTournamentResults(id, query);

  return (
    <>
      <PageHeader
        title={`Tournament ${id}`}
        description="Tournament summary is not exposed by the current API contract."
        source={result.ok ? result.source : undefined}
        actions={<ButtonLink href="/tournaments" variant="outline">Back to tournaments</ButtonLink>}
      />
      {!result.ok ? (
        <ErrorState message={result.error} />
      ) : result.data.length ? (
        <div className="flex flex-col gap-4">
          <TournamentResultsTable rows={result.data} />
          <PaginationControls pagination={result.pagination} params={queryParams} pathname={`/tournaments/${id}`} />
        </div>
      ) : (
        <EmptyState message="No result rows are available for this tournament." />
      )}
    </>
  );
}
