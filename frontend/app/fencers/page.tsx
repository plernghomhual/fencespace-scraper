import { FencerTable } from "@/components/DataTables";
import { Field, FilterBar, SelectFilter, TextFilter } from "@/components/Filters";
import { PageHeader } from "@/components/PageHeader";
import { PaginationControls } from "@/components/PaginationControls";
import { EmptyState, ErrorState } from "@/components/StatePanels";
import { Input } from "@/components/ui/input";
import { parseFencerSearchParams, searchFencers } from "@/lib/api";
import type { SearchParams } from "@/lib/types";
import { resolveSearchParams } from "@/lib/utils";

export default async function FencersPage({ searchParams }: { searchParams?: Promise<SearchParams> }) {
  const params = (await resolveSearchParams(searchParams)) || {};
  const query = parseFencerSearchParams(params);
  const result = await searchFencers(query);

  return (
    <>
      <PageHeader title="Fencers" description="Search by name, country code, and weapon." source={result.ok ? result.source : undefined} />
      <FilterBar>
        <TextFilter label="Name" name="name" placeholder="Alex Lee" value={query.name} />
        <TextFilter label="Country" name="country" placeholder="KOR" value={query.country} />
        <SelectFilter label="Weapon" name="weapon" options={["Epee", "Foil", "Sabre"]} value={query.weapon} />
        <Field label="Page size">
          <Input min={1} max={100} name="limit" type="number" defaultValue={query.limit} />
        </Field>
      </FilterBar>
      {!result.ok ? (
        <ErrorState message={result.error} />
      ) : result.data.length ? (
        <div className="flex flex-col gap-4">
          <FencerTable rows={result.data} />
          <PaginationControls pagination={result.pagination} params={params} pathname="/fencers" />
        </div>
      ) : (
        <EmptyState message="No fencers match the current filters." />
      )}
    </>
  );
}
