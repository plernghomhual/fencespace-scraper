import Link from "next/link";

import type { CountryDepth, Fencer, HeadToHeadRecord, Ranking, Tournament, TournamentResult } from "@/lib/types";
import { displayDate, formatNumber } from "@/lib/utils";

export function FencerTable({ rows }: { rows: Fencer[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table aria-label="Fencer results" className="w-full min-w-[720px] text-left text-sm">
        <thead className="bg-muted text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-4 py-3" scope="col">Name</th>
            <th className="px-4 py-3" scope="col">Country</th>
            <th className="px-4 py-3" scope="col">Weapon</th>
            <th className="px-4 py-3" scope="col">Category</th>
            <th className="px-4 py-3" scope="col">Rank</th>
            <th className="px-4 py-3" scope="col">Points</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row) => (
            <tr className="hover:bg-muted/40" key={row.id}>
              <td className="px-4 py-3 font-medium">
                <Link className="text-primary hover:underline" href={`/fencers/${row.id}`}>
                  {row.name || row.id}
                </Link>
              </td>
              <td className="px-4 py-3">{row.country || "—"}</td>
              <td className="px-4 py-3">{row.weapon || "—"}</td>
              <td className="px-4 py-3">{row.category || "—"}</td>
              <td className="px-4 py-3">{formatNumber(row.world_rank)}</td>
              <td className="px-4 py-3">{formatNumber(row.fie_points)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TournamentTable({ rows }: { rows: Tournament[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table aria-label="Tournament results" className="w-full min-w-[760px] text-left text-sm">
        <thead className="bg-muted text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-4 py-3" scope="col">Name</th>
            <th className="px-4 py-3" scope="col">Season</th>
            <th className="px-4 py-3" scope="col">Type</th>
            <th className="px-4 py-3" scope="col">Country</th>
            <th className="px-4 py-3" scope="col">Dates</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row) => (
            <tr className="hover:bg-muted/40" key={row.id}>
              <td className="px-4 py-3 font-medium">
                <Link className="text-primary hover:underline" href={`/tournaments/${row.id}`}>
                  {row.name || row.id}
                </Link>
              </td>
              <td className="px-4 py-3">{formatNumber(row.season)}</td>
              <td className="px-4 py-3">{row.type || "—"}</td>
              <td className="px-4 py-3">{row.country || "—"}</td>
              <td className="px-4 py-3">{displayDate(row.start_date)} to {displayDate(row.end_date)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RankingTable({ rows }: { rows: Ranking[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table aria-label="Ranking rows" className="w-full min-w-[720px] text-left text-sm">
        <thead className="bg-muted text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-4 py-3" scope="col">Rank</th>
            <th className="px-4 py-3" scope="col">Name</th>
            <th className="px-4 py-3" scope="col">Season</th>
            <th className="px-4 py-3" scope="col">Weapon</th>
            <th className="px-4 py-3" scope="col">Gender</th>
            <th className="px-4 py-3" scope="col">Category</th>
            <th className="px-4 py-3" scope="col">Points</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row, index) => (
            <tr className="hover:bg-muted/40" key={`${row.season}-${row.weapon}-${row.gender}-${row.category}-${row.rank}-${index}`}>
              <td className="px-4 py-3 font-medium">{formatNumber(row.rank)}</td>
              <td className="px-4 py-3">{row.name || "—"}</td>
              <td className="px-4 py-3">{formatNumber(row.season)}</td>
              <td className="px-4 py-3">{row.weapon || "—"}</td>
              <td className="px-4 py-3">{row.gender || "—"}</td>
              <td className="px-4 py-3">{row.category || "—"}</td>
              <td className="px-4 py-3">{formatNumber(row.points)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TournamentResultsTable({ rows }: { rows: TournamentResult[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table aria-label="Tournament result rows" className="w-full min-w-[620px] text-left text-sm">
        <thead className="bg-muted text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-4 py-3" scope="col">Rank</th>
            <th className="px-4 py-3" scope="col">Name</th>
            <th className="px-4 py-3" scope="col">Nationality</th>
            <th className="px-4 py-3" scope="col">Fencer ID</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row, index) => (
            <tr className="hover:bg-muted/40" key={`${row.tournament_id}-${row.rank}-${row.name}-${index}`}>
              <td className="px-4 py-3 font-medium">{formatNumber(row.rank)}</td>
              <td className="px-4 py-3">{row.name || "—"}</td>
              <td className="px-4 py-3">{row.nationality || "—"}</td>
              <td className="px-4 py-3">{row.fencer_id || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CountryDepthTable({ rows }: { rows: CountryDepth[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table aria-label="Country depth rows" className="w-full min-w-[720px] text-left text-sm">
        <thead className="bg-muted text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-4 py-3" scope="col">Weapon</th>
            <th className="px-4 py-3" scope="col">Category</th>
            <th className="px-4 py-3" scope="col">Top 16</th>
            <th className="px-4 py-3" scope="col">Top 32</th>
            <th className="px-4 py-3" scope="col">Top 64</th>
            <th className="px-4 py-3" scope="col">Ranked</th>
            <th className="px-4 py-3" scope="col">Avg rank</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row, index) => (
            <tr className="hover:bg-muted/40" key={`${row.country}-${row.weapon}-${row.category}-${index}`}>
              <td className="px-4 py-3 font-medium">{row.weapon || "—"}</td>
              <td className="px-4 py-3">{row.category || "—"}</td>
              <td className="px-4 py-3">{formatNumber(row.fencers_in_top16)}</td>
              <td className="px-4 py-3">{formatNumber(row.fencers_in_top32)}</td>
              <td className="px-4 py-3">{formatNumber(row.fencers_in_top64)}</td>
              <td className="px-4 py-3">{formatNumber(row.total_ranked)}</td>
              <td className="px-4 py-3">{formatNumber(row.avg_world_rank)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function HeadToHeadTable({ rows }: { rows: HeadToHeadRecord[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table aria-label="Head-to-head rows" className="w-full min-w-[700px] text-left text-sm">
        <thead className="bg-muted text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-4 py-3" scope="col">Weapon</th>
            <th className="px-4 py-3" scope="col">A wins</th>
            <th className="px-4 py-3" scope="col">B wins</th>
            <th className="px-4 py-3" scope="col">Bouts</th>
            <th className="px-4 py-3" scope="col">Touches</th>
            <th className="px-4 py-3" scope="col">Last meeting</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row, index) => (
            <tr className="hover:bg-muted/40" key={`${row.weapon}-${index}`}>
              <td className="px-4 py-3 font-medium">{row.weapon || "—"}</td>
              <td className="px-4 py-3">{formatNumber(row.a_wins)}</td>
              <td className="px-4 py-3">{formatNumber(row.b_wins)}</td>
              <td className="px-4 py-3">{formatNumber(row.bouts_total)}</td>
              <td className="px-4 py-3">{formatNumber(row.a_touches)} / {formatNumber(row.b_touches)}</td>
              <td className="px-4 py-3">{displayDate(row.last_meeting_date)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
