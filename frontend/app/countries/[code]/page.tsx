import { CountryDepthTable } from "@/components/DataTables";
import { Field, FilterBar } from "@/components/Filters";
import { PageHeader } from "@/components/PageHeader";
import { PaginationControls } from "@/components/PaginationControls";
import { EmptyState, ErrorState } from "@/components/StatePanels";
import { Input } from "@/components/ui/input";
import { getCountryDepth, parsePaginationParams } from "@/lib/api";
import type { SearchParams } from "@/lib/types";
import { resolveRouteParams, resolveSearchParams } from "@/lib/utils";

export default async function CountryPage({
  params,
  searchParams,
}: {
  params: Promise<{ code: string }>;
  searchParams?: Promise<SearchParams>;
}) {
  const [{ code }, paramsObj] = await Promise.all([resolveRouteParams(params), resolveSearchParams(searchParams)]);
  const country = code.toUpperCase();
  const queryParams = paramsObj || {};
  const query = parsePaginationParams(queryParams);
  const result = await getCountryDepth(country, query);

  return (
    <>
      <PageHeader title={`${country} fencing depth`} description="Country depth rows by weapon and category." source={result.ok ? result.source : undefined} />
      <FilterBar>
        <Field label="Page size">
          <Input min={1} max={100} name="limit" type="number" defaultValue={query.limit} />
        </Field>
        <Field label="Offset">
          <Input min={0} name="offset" type="number" defaultValue={query.offset} />
        </Field>
      </FilterBar>
      {!result.ok ? (
        <ErrorState message={result.error} />
      ) : result.data.length ? (
        <div className="flex flex-col gap-4">
          <CountryDepthTable rows={result.data} />
          <PaginationControls pagination={result.pagination} params={queryParams} pathname={`/countries/${country}`} />
        </div>
      ) : (
        <EmptyState message="No country depth rows are available for this country." />
      )}
    </>
  );
}
