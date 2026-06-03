import { TournamentTable } from "@/components/DataTables";
import { Field, FilterBar, TextFilter } from "@/components/Filters";
import { PageHeader } from "@/components/PageHeader";
import { PaginationControls } from "@/components/PaginationControls";
import { EmptyState, ErrorState } from "@/components/StatePanels";
import { Input } from "@/components/ui/input";
import { listTournaments, parseTournamentSearchParams } from "@/lib/api";
import type { SearchParams } from "@/lib/types";
import { resolveSearchParams } from "@/lib/utils";

export default async function TournamentsPage({ searchParams }: { searchParams?: Promise<SearchParams> }) {
  const params = (await resolveSearchParams(searchParams)) || {};
  const query = parseTournamentSearchParams(params);
  const result = await listTournaments(query);

  return (
    <>
      <PageHeader title="Tournaments" description="Browse tournaments by season, type, and country." source={result.ok ? result.source : undefined} />
      <FilterBar>
        <Field label="Season">
          <Input defaultValue={query.season || ""} min={1900} name="season" type="number" />
        </Field>
        <TextFilter label="Type" name="type" placeholder="GP" value={query.type} />
        <TextFilter label="Country" name="country" placeholder="KOR" value={query.country} />
        <Field label="Page size">
          <Input min={1} max={100} name="limit" type="number" defaultValue={query.limit} />
        </Field>
      </FilterBar>
      {!result.ok ? (
        <ErrorState message={result.error} />
      ) : result.data.length ? (
        <div className="flex flex-col gap-4">
          <TournamentTable rows={result.data} />
          <PaginationControls pagination={result.pagination} params={params} pathname="/tournaments" />
        </div>
      ) : (
        <EmptyState message="No tournaments match the current filters." />
      )}
    </>
  );
}
