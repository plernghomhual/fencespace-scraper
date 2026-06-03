import { RankingTable } from "@/components/DataTables";
import { Field, FilterBar, SelectFilter } from "@/components/Filters";
import { PageHeader } from "@/components/PageHeader";
import { PaginationControls } from "@/components/PaginationControls";
import { EmptyState, ErrorState } from "@/components/StatePanels";
import { Input } from "@/components/ui/input";
import { listRankings, parseRankingSearchParams } from "@/lib/api";
import type { SearchParams } from "@/lib/types";
import { resolveSearchParams } from "@/lib/utils";

export default async function RankingsPage({ searchParams }: { searchParams?: Promise<SearchParams> }) {
  const params = (await resolveSearchParams(searchParams)) || {};
  const query = parseRankingSearchParams(params);
  const result = await listRankings(query);

  return (
    <>
      <PageHeader title="Rankings" description="Filter ranking rows by season, weapon, gender, and category." source={result.ok ? result.source : undefined} />
      <FilterBar>
        <Field label="Season">
          <Input defaultValue={query.season || ""} min={1900} name="season" type="number" />
        </Field>
        <SelectFilter label="Weapon" name="weapon" options={["Epee", "Foil", "Sabre"]} value={query.weapon} />
        <SelectFilter label="Gender" name="gender" options={["Men", "Women"]} value={query.gender} />
        <SelectFilter label="Category" name="category" options={["Senior", "Junior", "Cadet", "Veteran"]} value={query.category} />
      </FilterBar>
      {!result.ok ? (
        <ErrorState message={result.error} />
      ) : result.data.length ? (
        <div className="flex flex-col gap-4">
          <RankingTable rows={result.data} />
          <PaginationControls pagination={result.pagination} params={params} pathname="/rankings" />
        </div>
      ) : (
        <EmptyState message="No rankings match the current filters." />
      )}
    </>
  );
}
