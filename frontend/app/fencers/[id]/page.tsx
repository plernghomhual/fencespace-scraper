import { PageHeader } from "@/components/PageHeader";
import { EmptyState, ErrorState } from "@/components/StatePanels";
import { ButtonLink } from "@/components/ui/button";
import { getFencerProfile } from "@/lib/api";
import { formatNumber, resolveRouteParams } from "@/lib/utils";

export default async function FencerDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await resolveRouteParams(params);
  const result = await getFencerProfile(id);

  if (!result.ok) {
    return (
      <>
        <PageHeader title="Fencer profile" actions={<ButtonLink href="/fencers" variant="outline">Back to fencers</ButtonLink>} />
        <ErrorState message={result.error} />
      </>
    );
  }

  const profile = result.data.profile;
  const stats = result.data.career_stats || {};

  return (
    <>
      <PageHeader
        title={profile.name || profile.id}
        description={`${profile.country || "Unknown country"} · ${profile.weapon || "Unknown weapon"} · ${profile.category || "Unknown category"}`}
        source={result.source}
        actions={<ButtonLink href="/fencers" variant="outline">Back to fencers</ButtonLink>}
      />
      <section className="grid gap-4 md:grid-cols-4">
        <Metric label="World rank" value={formatNumber(profile.world_rank)} />
        <Metric label="FIE points" value={formatNumber(profile.fie_points)} />
        <Metric label="Competitions" value={formatNumber(Number(stats.total_competitions))} />
        <Metric label="Best rank" value={formatNumber(Number(stats.best_world_rank))} />
      </section>
      {result.data.social.length || result.data.equipment.length ? (
        <section className="grid gap-4 md:grid-cols-2">
          <RecordList title="Social" rows={result.data.social} />
          <RecordList title="Equipment" rows={result.data.equipment} />
        </section>
      ) : (
        <EmptyState message="No social or equipment records are available for this fencer." />
      )}
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function RecordList({ title, rows }: { title: string; rows: Array<Record<string, unknown>> }) {
  return (
    <section className="rounded-lg border border-border bg-background p-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      <dl className="mt-4 flex flex-col gap-3 text-sm">
        {rows.map((row, index) => (
          <div className="rounded-md bg-muted p-3" key={index}>
            {Object.entries(row).map(([key, value]) => (
              <div className="grid gap-1 sm:grid-cols-3" key={key}>
                <dt className="text-muted-foreground">{key}</dt>
                <dd className="sm:col-span-2">{String(value ?? "—")}</dd>
              </div>
            ))}
          </div>
        ))}
      </dl>
    </section>
  );
}
