import type { GetServerSideProps, NextPage } from "next";

import { AppShell } from "@/components/AppShell";
import { HeadToHeadTable } from "@/components/DataTables";
import { Field, FilterBar } from "@/components/Filters";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanels";
import { Input } from "@/components/ui/input";
import { getHeadToHead } from "@/lib/api";
import type { ApiItemResult, HeadToHeadPayload } from "@/lib/types";

type Props = {
  fencerA: string;
  fencerB: string;
  result: ApiItemResult<HeadToHeadPayload> | null;
};

function firstQueryValue(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return value[0] || "";
  }
  return value || "";
}

export const getServerSideProps: GetServerSideProps<Props> = async ({ query }) => {
  const fencerA = firstQueryValue(query.fencerA || query.a).trim();
  const fencerB = firstQueryValue(query.fencerB || query.b).trim();
  const result = fencerA && fencerB ? await getHeadToHead(fencerA, fencerB) : null;

  return {
    props: {
      fencerA,
      fencerB,
      result,
    },
  };
};

const HeadToHeadPage: NextPage<Props> = ({ fencerA, fencerB, result }) => {
  return (
    <AppShell>
      <PageHeader title="Head-to-head" description="Compare two fencers by FenceSpace fencer ID." source={result?.ok ? result.source : undefined} />
      <FilterBar>
        <Field label="Fencer A ID">
          <Input defaultValue={fencerA} name="fencerA" placeholder="f1" />
        </Field>
        <Field label="Fencer B ID">
          <Input defaultValue={fencerB} name="fencerB" placeholder="f2" />
        </Field>
      </FilterBar>
      {!result ? (
        <EmptyState message="Enter two fencer IDs to load head-to-head records." />
      ) : !result.ok ? (
        <ErrorState message={result.error} />
      ) : result.data.data.length ? (
        <HeadToHeadTable rows={result.data.data} />
      ) : (
        <EmptyState message="No head-to-head records are available for this pair." />
      )}
    </AppShell>
  );
};

export default HeadToHeadPage;
