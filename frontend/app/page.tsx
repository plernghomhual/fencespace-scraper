import { ButtonLink } from "@/components/ui/button";
import { FencerTable, RankingTable, TournamentTable } from "@/components/DataTables";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanels";
import { listRankings, listTournaments, parseFencerSearchParams, parseRankingSearchParams, parseTournamentSearchParams, searchFencers } from "@/lib/api";

export default async function HomePage() {
  const [fencers, tournaments, rankings] = await Promise.all([
    searchFencers(parseFencerSearchParams({ limit: "5" })),
    listTournaments(parseTournamentSearchParams({ limit: "5" })),
    listRankings(parseRankingSearchParams({ limit: "5" })),
  ]);

  return (
    <>
      <PageHeader
        title="FenceSpace Explorer"
        description="Search fencers, tournaments, rankings, country depth, and head-to-head records from the public FenceSpace contract."
        actions={
          <>
            <ButtonLink href="/fencers">Browse fencers</ButtonLink>
            <ButtonLink href="/tournaments" variant="outline">Browse tournaments</ButtonLink>
          </>
        }
        source={fencers.ok ? fencers.source : undefined}
      />

      <section className="grid gap-6 lg:grid-cols-3">
        <ButtonLink className="h-auto justify-start px-5 py-4" href="/rankings" variant="secondary">Rankings</ButtonLink>
        <ButtonLink className="h-auto justify-start px-5 py-4" href="/countries/KOR" variant="secondary">Country depth</ButtonLink>
        <ButtonLink className="h-auto justify-start px-5 py-4" href="/head-to-head" variant="secondary">Head-to-head</ButtonLink>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-xl font-semibold">Fencers</h2>
        {!fencers.ok ? <ErrorState message={fencers.error} /> : fencers.data.length ? <FencerTable rows={fencers.data} /> : <EmptyState message="No fencers are available." />}
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-xl font-semibold">Tournaments</h2>
        {!tournaments.ok ? <ErrorState message={tournaments.error} /> : tournaments.data.length ? <TournamentTable rows={tournaments.data} /> : <EmptyState message="No tournaments are available." />}
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-xl font-semibold">Rankings</h2>
        {!rankings.ok ? <ErrorState message={rankings.error} /> : rankings.data.length ? <RankingTable rows={rankings.data} /> : <EmptyState message="No rankings are available." />}
      </section>
    </>
  );
}
