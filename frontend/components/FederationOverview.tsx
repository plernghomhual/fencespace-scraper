import React from "react";

export type FederationCountry = {
  alpha3: string;
  iso3?: string;
  alpha2?: string;
  olympicCode?: string;
  fieCode?: string;
  name: string;
  flag?: string;
  aliases: string[];
};

export type FencerSummary = {
  id?: string;
  name: string;
  country?: string;
  weapon?: string;
  category?: string;
  worldRank?: number | null;
  domesticRank?: number | null;
  club?: string | null;
  fiePoints?: number | null;
};

export type CountryDepthRow = {
  country?: string;
  weapon: string;
  category: string;
  fencersInTop16: number;
  fencersInTop32: number;
  fencersInTop64: number;
  totalRanked: number;
  avgWorldRank?: number | null;
};

export type MedalRow = {
  scope: "country" | "tier_country" | string;
  country?: string | null;
  tier?: string | null;
  gold: number;
  silver: number;
  bronze: number;
  total: number;
};

export type ClubRankingRow = {
  club: string;
  country?: string;
  weapon?: string;
  totalFencers: number;
  avgRank?: number | null;
  totalPoints?: number | null;
};

export type NationalRankingRow = {
  country?: string;
  weapon: string;
  category: string;
  fencerCount: number;
  top8Count: number;
};

export type TournamentSummary = {
  id?: string;
  name: string;
  country?: string | null;
  weapon?: string | null;
  category?: string | null;
  type?: string | null;
  startDate?: string | null;
  endDate?: string | null;
};

export type FederationOverviewData = {
  federation: {
    code: string;
    name: string;
    flag?: string;
  };
  topFencers: FencerSummary[];
  depthRows: CountryDepthRow[];
  medalRows: MedalRow[];
  clubRows: ClubRankingRow[];
  nationalRankingRows: NationalRankingRow[];
  recentTournaments: TournamentSummary[];
};

export type FederationOverviewProps = {
  data: FederationOverviewData;
  preferTables?: boolean;
};

export const FEDERATION_COUNTRIES: FederationCountry[] = [
  { alpha3: "AND", alpha2: "AD", name: "Andorra", flag: "🇦🇩", aliases: ["AND", "AD", "Andorra"] },
  { alpha3: "ARG", alpha2: "AR", name: "Argentina", flag: "🇦🇷", aliases: ["ARG", "AR", "Argentina"] },
  { alpha3: "AUS", alpha2: "AU", name: "Australia", flag: "🇦🇺", aliases: ["AUS", "AU", "Australia"] },
  { alpha3: "AUT", alpha2: "AT", name: "Austria", flag: "🇦🇹", aliases: ["AUT", "AT", "Austria"] },
  { alpha3: "BEL", alpha2: "BE", name: "Belgium", flag: "🇧🇪", aliases: ["BEL", "BE", "Belgium"] },
  { alpha3: "BRA", alpha2: "BR", name: "Brazil", flag: "🇧🇷", aliases: ["BRA", "BR", "Brazil"] },
  { alpha3: "BUL", alpha2: "BG", name: "Bulgaria", flag: "🇧🇬", aliases: ["BUL", "BG", "Bulgaria"] },
  { alpha3: "CAN", alpha2: "CA", name: "Canada", flag: "🇨🇦", aliases: ["CAN", "CA", "Canada"] },
  { alpha3: "CHN", alpha2: "CN", name: "China", flag: "🇨🇳", aliases: ["CHN", "CN", "China", "People's Republic of China"] },
  { alpha3: "COL", alpha2: "CO", name: "Colombia", flag: "🇨🇴", aliases: ["COL", "CO", "Colombia"] },
  { alpha3: "HRV", alpha2: "HR", olympicCode: "CRO", fieCode: "CRO", name: "Croatia", flag: "🇭🇷", aliases: ["CRO", "HR", "HRV", "Croatia"] },
  { alpha3: "CZE", alpha2: "CZ", iso3: "CZE", name: "Czechia", flag: "🇨🇿", aliases: ["CZE", "CZ", "Czech Republic", "Czechia"] },
  { alpha3: "DNK", alpha2: "DK", olympicCode: "DEN", fieCode: "DEN", name: "Denmark", flag: "🇩🇰", aliases: ["DEN", "DK", "DNK", "Denmark"] },
  { alpha3: "EGY", alpha2: "EG", name: "Egypt", flag: "🇪🇬", aliases: ["EGY", "EG", "Egypt"] },
  { alpha3: "ESP", alpha2: "ES", name: "Spain", flag: "🇪🇸", aliases: ["ESP", "ES", "Spain"] },
  { alpha3: "EST", alpha2: "EE", name: "Estonia", flag: "🇪🇪", aliases: ["EST", "EE", "Estonia"] },
  { alpha3: "FIN", alpha2: "FI", name: "Finland", flag: "🇫🇮", aliases: ["FIN", "FI", "Finland"] },
  { alpha3: "FRA", alpha2: "FR", name: "France", flag: "🇫🇷", aliases: ["FRA", "FR", "France"] },
  { alpha3: "GBR", alpha2: "GB", name: "Great Britain", flag: "🇬🇧", aliases: ["GBR", "GB", "UK", "United Kingdom", "Great Britain", "Britain"] },
  { alpha3: "DEU", alpha2: "DE", olympicCode: "GER", fieCode: "GER", name: "Germany", flag: "🇩🇪", aliases: ["GER", "DE", "DEU", "Germany"] },
  { alpha3: "GRC", alpha2: "GR", olympicCode: "GRE", fieCode: "GRE", name: "Greece", flag: "🇬🇷", aliases: ["GRE", "GR", "GRC", "Greece"] },
  { alpha3: "HKG", alpha2: "HK", name: "Hong Kong", flag: "🇭🇰", aliases: ["HKG", "HK", "Hong Kong"] },
  { alpha3: "HUN", alpha2: "HU", name: "Hungary", flag: "🇭🇺", aliases: ["HUN", "HU", "Hungary"] },
  { alpha3: "IND", alpha2: "IN", name: "India", flag: "🇮🇳", aliases: ["IND", "IN", "India"] },
  { alpha3: "IRL", alpha2: "IE", name: "Ireland", flag: "🇮🇪", aliases: ["IRL", "IE", "Ireland"] },
  { alpha3: "ISR", alpha2: "IL", name: "Israel", flag: "🇮🇱", aliases: ["ISR", "IL", "Israel"] },
  { alpha3: "ITA", alpha2: "IT", name: "Italy", flag: "🇮🇹", aliases: ["ITA", "IT", "Italy"] },
  { alpha3: "JPN", alpha2: "JP", name: "Japan", flag: "🇯🇵", aliases: ["JPN", "JP", "Japan"] },
  { alpha3: "KAZ", alpha2: "KZ", name: "Kazakhstan", flag: "🇰🇿", aliases: ["KAZ", "KZ", "Kazakhstan"] },
  { alpha3: "KOR", alpha2: "KR", name: "Korea", flag: "🇰🇷", aliases: ["KOR", "KR", "Korea", "South Korea", "Republic of Korea"] },
  { alpha3: "SAU", alpha2: "SA", olympicCode: "KSA", fieCode: "KSA", name: "Saudi Arabia", flag: "🇸🇦", aliases: ["KSA", "SA", "SAU", "Saudi Arabia"] },
  { alpha3: "LVA", alpha2: "LV", olympicCode: "LAT", fieCode: "LAT", name: "Latvia", flag: "🇱🇻", aliases: ["LAT", "LV", "LVA", "Latvia"] },
  { alpha3: "LTU", alpha2: "LT", name: "Lithuania", flag: "🇱🇹", aliases: ["LTU", "LT", "Lithuania"] },
  { alpha3: "MYS", alpha2: "MY", olympicCode: "MAS", fieCode: "MAS", name: "Malaysia", flag: "🇲🇾", aliases: ["MAS", "MY", "MYS", "Malaysia"] },
  { alpha3: "MAR", alpha2: "MA", name: "Morocco", flag: "🇲🇦", aliases: ["MAR", "MA", "Morocco"] },
  { alpha3: "MEX", alpha2: "MX", name: "Mexico", flag: "🇲🇽", aliases: ["MEX", "MX", "Mexico"] },
  { alpha3: "NLD", alpha2: "NL", olympicCode: "NED", fieCode: "NED", name: "Netherlands", flag: "🇳🇱", aliases: ["NED", "NL", "NLD", "Netherlands", "Holland"] },
  { alpha3: "NOR", alpha2: "NO", name: "Norway", flag: "🇳🇴", aliases: ["NOR", "NO", "Norway"] },
  { alpha3: "NZL", alpha2: "NZ", name: "New Zealand", flag: "🇳🇿", aliases: ["NZL", "NZ", "New Zealand"] },
  { alpha3: "PHL", alpha2: "PH", olympicCode: "PHI", fieCode: "PHI", name: "Philippines", flag: "🇵🇭", aliases: ["PHI", "PH", "PHL", "Philippines"] },
  { alpha3: "POL", alpha2: "PL", name: "Poland", flag: "🇵🇱", aliases: ["POL", "PL", "Poland"] },
  { alpha3: "PRT", alpha2: "PT", olympicCode: "POR", fieCode: "POR", name: "Portugal", flag: "🇵🇹", aliases: ["POR", "PT", "PRT", "Portugal"] },
  { alpha3: "QAT", alpha2: "QA", name: "Qatar", flag: "🇶🇦", aliases: ["QAT", "QA", "Qatar"] },
  { alpha3: "ROU", alpha2: "RO", name: "Romania", flag: "🇷🇴", aliases: ["ROU", "RO", "Romania"] },
  { alpha3: "ZAF", alpha2: "ZA", olympicCode: "RSA", fieCode: "RSA", name: "South Africa", flag: "🇿🇦", aliases: ["RSA", "ZA", "ZAF", "South Africa"] },
  { alpha3: "RUS", alpha2: "RU", name: "Russia", flag: "🇷🇺", aliases: ["RUS", "RU", "Russia"] },
  { alpha3: "SGP", alpha2: "SG", name: "Singapore", flag: "🇸🇬", aliases: ["SGP", "SG", "Singapore"] },
  { alpha3: "SVN", alpha2: "SI", olympicCode: "SLO", fieCode: "SLO", name: "Slovenia", flag: "🇸🇮", aliases: ["SLO", "SI", "SVN", "Slovenia"] },
  { alpha3: "SRB", alpha2: "RS", name: "Serbia", flag: "🇷🇸", aliases: ["SRB", "RS", "Serbia"] },
  { alpha3: "CHE", alpha2: "CH", olympicCode: "SUI", fieCode: "SUI", name: "Switzerland", flag: "🇨🇭", aliases: ["SUI", "CH", "CHE", "Switzerland"] },
  { alpha3: "SVK", alpha2: "SK", name: "Slovakia", flag: "🇸🇰", aliases: ["SVK", "SK", "Slovakia"] },
  { alpha3: "SWE", alpha2: "SE", name: "Sweden", flag: "🇸🇪", aliases: ["SWE", "SE", "Sweden"] },
  { alpha3: "THA", alpha2: "TH", name: "Thailand", flag: "🇹🇭", aliases: ["THA", "TH", "Thailand"] },
  { alpha3: "TUN", alpha2: "TN", name: "Tunisia", flag: "🇹🇳", aliases: ["TUN", "TN", "Tunisia"] },
  { alpha3: "TUR", alpha2: "TR", name: "Turkey", flag: "🇹🇷", aliases: ["TUR", "TR", "Turkey", "Türkiye"] },
  { alpha3: "ARE", alpha2: "AE", olympicCode: "UAE", fieCode: "UAE", name: "United Arab Emirates", flag: "🇦🇪", aliases: ["UAE", "AE", "ARE", "United Arab Emirates"] },
  { alpha3: "UKR", alpha2: "UA", name: "Ukraine", flag: "🇺🇦", aliases: ["UKR", "UA", "Ukraine"] },
  { alpha3: "USA", alpha2: "US", name: "United States", flag: "🇺🇸", aliases: ["USA", "US", "United States", "America"] },
  { alpha3: "UZB", alpha2: "UZ", name: "Uzbekistan", flag: "🇺🇿", aliases: ["UZB", "UZ", "Uzbekistan"] },
  { alpha3: "VNM", alpha2: "VN", olympicCode: "VIE", fieCode: "VIE", name: "Vietnam", flag: "🇻🇳", aliases: ["VIE", "VN", "VNM", "Vietnam"] },
];

const countryIndex = new Map<string, FederationCountry>();

for (const country of FEDERATION_COUNTRIES) {
  const keys = [country.alpha3, country.iso3, country.alpha2, country.olympicCode, country.fieCode, country.name, ...country.aliases];
  for (const key of keys) {
    if (key) {
      countryIndex.set(normalizeCountryKey(key), country);
    }
  }
}

export function getFederationCountry(code: string | null | undefined): FederationCountry | null {
  const key = normalizeCountryKey(code);
  return key ? countryIndex.get(key) ?? null : null;
}

export function sanitizeFederationPageData(input: unknown): FederationOverviewData {
  const raw = asRecord(input);
  const rawFederation = asRecord(raw.federation);
  const country = getFederationCountry(toText(rawFederation.code) ?? toText(rawFederation.alpha3));
  const code = country?.alpha3 ?? toText(rawFederation.code)?.toUpperCase() ?? "";
  const name = country?.name ?? toText(rawFederation.name) ?? code;

  return {
    federation: {
      code,
      name,
      flag: country?.flag ?? toText(rawFederation.flag) ?? undefined,
    },
    topFencers: asArray(raw.topFencers).map(sanitizeFencer).filter((row): row is FencerSummary => Boolean(row)),
    depthRows: asArray(raw.depthRows).map(sanitizeDepthRow).filter((row): row is CountryDepthRow => Boolean(row)),
    medalRows: asArray(raw.medalRows).map(sanitizeMedalRow).filter((row): row is MedalRow => Boolean(row)),
    clubRows: asArray(raw.clubRows).map(sanitizeClubRow).filter((row): row is ClubRankingRow => Boolean(row)),
    nationalRankingRows: asArray(raw.nationalRankingRows)
      .map(sanitizeNationalRankingRow)
      .filter((row): row is NationalRankingRow => Boolean(row)),
    recentTournaments: asArray(raw.recentTournaments)
      .map(sanitizeTournament)
      .filter((row): row is TournamentSummary => Boolean(row)),
  };
}

export default function FederationOverview({ data, preferTables = false }: FederationOverviewProps) {
  const sanitized = sanitizeFederationPageData(data);
  const { federation, topFencers, depthRows, medalRows, clubRows, nationalRankingRows, recentTournaments } = sanitized;
  const depthTotals = computeDepthTotals(depthRows);
  const countryMedals = medalRows.find((row) => row.scope === "country") ?? null;
  const tierMedals = medalRows.filter((row) => row.scope !== "country" && row.total > 0).slice(0, 6);
  const hasAnyData =
    topFencers.length > 0 ||
    depthRows.length > 0 ||
    medalRows.length > 0 ||
    clubRows.length > 0 ||
    nationalRankingRows.length > 0 ||
    recentTournaments.length > 0;

  return (
    <main className="federation-page" aria-labelledby="federation-title">
      <section className="hero">
        <div>
          <p className="eyebrow">{federation.code || "Federation"}</p>
          <h1 id="federation-title">
            <span aria-hidden="true" className="flag">
              {federation.flag}
            </span>
            {federation.name} Federation
          </h1>
        </div>
        <div className="hero-metrics" aria-label="Federation summary">
          <Metric label="Ranked fencers" value={`${formatNumber(depthTotals.totalRanked)} ranked fencers`} />
          <Metric label="Top 16 depth" value={formatNumber(depthTotals.top16)} />
          <Metric label="Medals" value={countryMedals ? `${formatNumber(countryMedals.total)} medals` : "No medals"} />
        </div>
      </section>

      {!hasAnyData ? (
        <section className="empty-state">
          <h2>No federation analytics are available yet for {federation.name}.</h2>
          <p>Depth, medal, ranking, club, and tournament data will appear after public data is processed.</p>
        </section>
      ) : (
        <>
          <section className="overview-grid">
            <Panel title="Top fencers">
              {topFencers.length > 0 ? (
                <ol className="fencer-list">
                  {topFencers.slice(0, 10).map((fencer) => (
                    <li key={fencer.id ?? `${fencer.name}-${fencer.weapon}-${fencer.category}`}>
                      <div>
                        <strong>{fencer.name}</strong>
                        <span>{joinParts([fencer.weapon, fencer.category, fencer.club])}</span>
                      </div>
                      <div className="rank-stack">
                        {fencer.worldRank ? <span>World {formatRank(fencer.worldRank)}</span> : null}
                        {fencer.domesticRank ? <span>Domestic {formatRank(fencer.domesticRank)}</span> : null}
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <EmptyLine>No top fencers are available for this federation yet.</EmptyLine>
              )}
            </Panel>

            <Panel title="Medals">
              {countryMedals ? (
                <div className="medal-summary">
                  <strong>{formatNumber(countryMedals.total)} medals</strong>
                  <div className="medal-row">
                    <span>Gold {formatNumber(countryMedals.gold)}</span>
                    <span>Silver {formatNumber(countryMedals.silver)}</span>
                    <span>Bronze {formatNumber(countryMedals.bronze)}</span>
                  </div>
                </div>
              ) : (
                <EmptyLine>No medal totals are available yet.</EmptyLine>
              )}

              {tierMedals.length > 0 ? (
                <table aria-label="Medals by tournament tier">
                  <thead>
                    <tr>
                      <th>Tier</th>
                      <th>Total</th>
                      <th>G</th>
                      <th>S</th>
                      <th>B</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tierMedals.map((row) => (
                      <tr key={`${row.tier}-${row.total}`}>
                        <td>{row.tier ?? "Other"}</td>
                        <td>{formatNumber(row.total)}</td>
                        <td>{formatNumber(row.gold)}</td>
                        <td>{formatNumber(row.silver)}</td>
                        <td>{formatNumber(row.bronze)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}
            </Panel>
          </section>

          <section className="analytics-grid">
            <Panel title="Top depth">
              {depthRows.length > 0 ? (
                preferTables ? (
                  <DepthTable rows={depthRows} />
                ) : (
                  <DepthChart totals={depthTotals} />
                )
              ) : (
                <EmptyLine>No top-16, top-32, or top-64 depth data is available yet.</EmptyLine>
              )}
            </Panel>

            <Panel title="Weapon and gender splits">
              {depthRows.length > 0 ? (
                preferTables ? (
                  <SplitTable rows={depthRows} />
                ) : (
                  <SplitChart rows={depthRows} />
                )
              ) : (
                <EmptyLine>No weapon or gender split data is available yet.</EmptyLine>
              )}
            </Panel>
          </section>

          <section className="overview-grid">
            <Panel title="National rankings">
              {nationalRankingRows.length > 0 ? (
                <table aria-label="National ranking coverage">
                  <thead>
                    <tr>
                      <th>Weapon</th>
                      <th>Category</th>
                      <th>Fencers</th>
                      <th>Top 8</th>
                    </tr>
                  </thead>
                  <tbody>
                    {nationalRankingRows.map((row) => (
                      <tr key={`${row.weapon}-${row.category}`}>
                        <td>{row.weapon}</td>
                        <td>{row.category}</td>
                        <td>{formatNumber(row.fencerCount)}</td>
                        <td>{formatNumber(row.top8Count)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <EmptyLine>No national ranking data is available for this federation yet.</EmptyLine>
              )}
            </Panel>

            <Panel title="Top clubs">
              {clubRows.length > 0 ? (
                <table aria-label="Top clubs">
                  <thead>
                    <tr>
                      <th>Club</th>
                      <th>Weapon</th>
                      <th>Fencers</th>
                      <th>Avg rank</th>
                    </tr>
                  </thead>
                  <tbody>
                    {clubRows.slice(0, 8).map((row) => (
                      <tr key={`${row.club}-${row.weapon}`}>
                        <td>{row.club}</td>
                        <td>{row.weapon ?? "All"}</td>
                        <td>{formatNumber(row.totalFencers)}</td>
                        <td>{row.avgRank ? row.avgRank.toFixed(1) : "n/a"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <EmptyLine>No club ranking data is available yet.</EmptyLine>
              )}
            </Panel>
          </section>

          <Panel title="Recent tournaments">
            {recentTournaments.length > 0 ? (
              <table aria-label="Recent tournaments">
                <thead>
                  <tr>
                    <th>Tournament</th>
                    <th>Date</th>
                    <th>Weapon</th>
                    <th>Category</th>
                    <th>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {recentTournaments.slice(0, 10).map((tournament) => (
                    <tr key={tournament.id ?? `${tournament.name}-${tournament.startDate}`}>
                      <td>{tournament.name}</td>
                      <td>{formatDate(tournament.startDate ?? tournament.endDate)}</td>
                      <td>{tournament.weapon ?? "Mixed"}</td>
                      <td>{tournament.category ?? "Open"}</td>
                      <td>{tournament.type ?? "Tournament"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <EmptyLine>No recent tournaments are available yet.</EmptyLine>
            )}
          </Panel>
        </>
      )}

      <style>{styles}</style>
    </main>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EmptyLine({ children }: { children: React.ReactNode }) {
  return <p className="empty-line">{children}</p>;
}

function DepthChart({ totals }: { totals: DepthTotals }) {
  const bars = [
    { label: "Top 16", value: totals.top16, className: "bar-green" },
    { label: "Top 32", value: totals.top32, className: "bar-gold" },
    { label: "Top 64", value: totals.top64, className: "bar-red" },
  ];
  const max = Math.max(...bars.map((bar) => bar.value), 1);

  return (
    <div role="img" aria-label="Top-16 top-32 top-64 depth chart" className="bar-chart">
      {bars.map((bar) => (
        <div className="bar-row" key={bar.label}>
          <span>{bar.label}</span>
          <div className="bar-track">
            <div className={`bar-fill ${bar.className}`} style={{ width: `${Math.max((bar.value / max) * 100, bar.value > 0 ? 8 : 0)}%` }} />
          </div>
          <strong>{formatNumber(bar.value)}</strong>
        </div>
      ))}
    </div>
  );
}

function SplitChart({ rows }: { rows: CountryDepthRow[] }) {
  const splits = computeSplitRows(rows);
  const max = Math.max(...splits.map((row) => row.fencersInTop64), 1);

  return (
    <div role="img" aria-label="Weapon and gender split chart" className="split-chart">
      {splits.map((row) => (
        <div className="split-row" key={`${row.weapon}-${row.category}`}>
          <span>{row.weapon}</span>
          <span>{row.category}</span>
          <div className="bar-track">
            <div className="bar-fill bar-blue" style={{ width: `${Math.max((row.fencersInTop64 / max) * 100, row.fencersInTop64 > 0 ? 8 : 0)}%` }} />
          </div>
          <strong>{formatNumber(row.fencersInTop64)}</strong>
        </div>
      ))}
    </div>
  );
}

function DepthTable({ rows }: { rows: CountryDepthRow[] }) {
  return (
    <table aria-label="Top depth table">
      <thead>
        <tr>
          <th>Weapon</th>
          <th>Category</th>
          <th>Top 16</th>
          <th>Top 32</th>
          <th>Top 64</th>
          <th>Total</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={`${row.weapon}-${row.category}`}>
            <td>{row.weapon}</td>
            <td>{row.category}</td>
            <td>{formatNumber(row.fencersInTop16)}</td>
            <td>{formatNumber(row.fencersInTop32)}</td>
            <td>{formatNumber(row.fencersInTop64)}</td>
            <td>{formatNumber(row.totalRanked)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SplitTable({ rows }: { rows: CountryDepthRow[] }) {
  return (
    <table aria-label="Weapon and gender split table">
      <thead>
        <tr>
          <th>Weapon</th>
          <th>Category</th>
          <th>Ranked</th>
          <th>Avg world rank</th>
        </tr>
      </thead>
      <tbody>
        {computeSplitRows(rows).map((row) => (
          <tr key={`${row.weapon}-${row.category}`}>
            <td>{row.weapon}</td>
            <td>{row.category}</td>
            <td>{formatNumber(row.totalRanked)}</td>
            <td>{row.avgWorldRank ? row.avgWorldRank.toFixed(1) : "n/a"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

type DepthTotals = {
  top16: number;
  top32: number;
  top64: number;
  totalRanked: number;
};

function computeDepthTotals(rows: CountryDepthRow[]): DepthTotals {
  return rows.reduce(
    (totals, row) => ({
      top16: totals.top16 + row.fencersInTop16,
      top32: totals.top32 + row.fencersInTop32,
      top64: totals.top64 + row.fencersInTop64,
      totalRanked: totals.totalRanked + row.totalRanked,
    }),
    { top16: 0, top32: 0, top64: 0, totalRanked: 0 },
  );
}

function computeSplitRows(rows: CountryDepthRow[]) {
  const grouped = new Map<string, CountryDepthRow & { avgTotal: number }>();
  for (const row of rows) {
    const key = `${row.weapon}::${row.category}`;
    const existing = grouped.get(key);
    if (existing) {
      existing.fencersInTop16 += row.fencersInTop16;
      existing.fencersInTop32 += row.fencersInTop32;
      existing.fencersInTop64 += row.fencersInTop64;
      existing.totalRanked += row.totalRanked;
      if (row.avgWorldRank) {
        existing.avgTotal += row.avgWorldRank;
        existing.avgWorldRank = existing.avgTotal / 2;
      }
    } else {
      grouped.set(key, { ...row, avgTotal: row.avgWorldRank ?? 0 });
    }
  }
  return [...grouped.values()].sort((a, b) => b.fencersInTop64 - a.fencersInTop64 || a.weapon.localeCompare(b.weapon));
}

function sanitizeFencer(input: unknown): FencerSummary | null {
  const raw = asRecord(input);
  const name = toText(raw.name);
  if (!name) {
    return null;
  }
  return {
    id: toText(raw.id) ?? undefined,
    name,
    country: toText(raw.country) ?? undefined,
    weapon: toText(raw.weapon) ?? undefined,
    category: toText(raw.category) ?? undefined,
    worldRank: toNumber(raw.worldRank ?? raw.world_rank),
    domesticRank: toNumber(raw.domesticRank ?? raw.domestic_rank),
    club: toText(raw.club),
    fiePoints: toNumber(raw.fiePoints ?? raw.fie_points),
  };
}

function sanitizeDepthRow(input: unknown): CountryDepthRow | null {
  const raw = asRecord(input);
  const weapon = toText(raw.weapon);
  const category = toText(raw.category);
  if (!weapon || !category) {
    return null;
  }
  return {
    country: toText(raw.country) ?? undefined,
    weapon,
    category,
    fencersInTop16: toInteger(raw.fencersInTop16 ?? raw.fencers_in_top16),
    fencersInTop32: toInteger(raw.fencersInTop32 ?? raw.fencers_in_top32),
    fencersInTop64: toInteger(raw.fencersInTop64 ?? raw.fencers_in_top64),
    totalRanked: toInteger(raw.totalRanked ?? raw.total_ranked),
    avgWorldRank: toNumber(raw.avgWorldRank ?? raw.avg_world_rank),
  };
}

function sanitizeMedalRow(input: unknown): MedalRow | null {
  const raw = asRecord(input);
  const scope = toText(raw.scope);
  if (!scope) {
    return null;
  }
  return {
    scope,
    country: toText(raw.country),
    tier: toText(raw.tier),
    gold: toInteger(raw.gold),
    silver: toInteger(raw.silver),
    bronze: toInteger(raw.bronze),
    total: toInteger(raw.total),
  };
}

function sanitizeClubRow(input: unknown): ClubRankingRow | null {
  const raw = asRecord(input);
  const club = toText(raw.club);
  if (!club) {
    return null;
  }
  return {
    club,
    country: toText(raw.country) ?? undefined,
    weapon: toText(raw.weapon) ?? undefined,
    totalFencers: toInteger(raw.totalFencers ?? raw.total_fencers),
    avgRank: toNumber(raw.avgRank ?? raw.avg_rank),
    totalPoints: toNumber(raw.totalPoints ?? raw.total_points),
  };
}

function sanitizeNationalRankingRow(input: unknown): NationalRankingRow | null {
  const raw = asRecord(input);
  const weapon = toText(raw.weapon);
  const category = toText(raw.category);
  if (!weapon || !category) {
    return null;
  }
  return {
    country: toText(raw.country) ?? undefined,
    weapon,
    category,
    fencerCount: toInteger(raw.fencerCount ?? raw.fencer_count),
    top8Count: toInteger(raw.top8Count ?? raw.top8_count),
  };
}

function sanitizeTournament(input: unknown): TournamentSummary | null {
  const raw = asRecord(input);
  const name = toText(raw.name);
  if (!name) {
    return null;
  }
  return {
    id: toText(raw.id) ?? undefined,
    name,
    country: toText(raw.country),
    weapon: toText(raw.weapon),
    category: toText(raw.category),
    type: toText(raw.type ?? raw.competition_type),
    startDate: toText(raw.startDate ?? raw.start_date),
    endDate: toText(raw.endDate ?? raw.end_date),
  };
}

function normalizeCountryKey(value: string | null | undefined): string {
  return String(value ?? "")
    .trim()
    .normalize("NFKD")
    .replace(/[^\p{Letter}\p{Number}]/gu, "")
    .toUpperCase();
}

function asRecord(input: unknown): Record<string, unknown> {
  return input && typeof input === "object" ? (input as Record<string, unknown>) : {};
}

function asArray(input: unknown): unknown[] {
  return Array.isArray(input) ? input : [];
}

function toText(input: unknown): string | null {
  if (typeof input !== "string" && typeof input !== "number") {
    return null;
  }
  const text = String(input).replace(/\s+/g, " ").trim();
  return text || null;
}

function toNumber(input: unknown): number | null {
  if (input === null || input === undefined || input === "") {
    return null;
  }
  const value = Number(input);
  return Number.isFinite(value) ? value : null;
}

function toInteger(input: unknown): number {
  const value = toNumber(input);
  return value && value > 0 ? Math.trunc(value) : 0;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatRank(rank: number): string {
  return `#${formatNumber(rank)}`;
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "TBD";
  }
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  const date = dateOnly
    ? new Date(Date.UTC(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3])))
    : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC", year: "numeric" }).format(date);
}

function joinParts(parts: Array<string | null | undefined>): string {
  return parts.filter((part): part is string => Boolean(part)).join(" · ") || "Ranking data";
}

const styles = `
.federation-page {
  color: #16211f;
  background: #f7f8f4;
  min-height: 100vh;
  padding: 32px;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: end;
  padding: 28px 0 24px;
  border-bottom: 1px solid #d7ded3;
}

.eyebrow {
  color: #496158;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0;
  margin: 0 0 8px;
  text-transform: uppercase;
}

h1 {
  align-items: center;
  display: flex;
  gap: 12px;
  font-size: clamp(2rem, 4vw, 3.5rem);
  line-height: 1;
  margin: 0;
}

h2 {
  font-size: 1rem;
  margin: 0 0 16px;
}

.flag {
  font-size: 0.9em;
}

.hero-metrics,
.overview-grid,
.analytics-grid {
  display: grid;
  gap: 16px;
}

.hero-metrics {
  grid-template-columns: repeat(3, minmax(120px, 1fr));
}

.overview-grid,
.analytics-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 20px;
}

.metric,
.panel,
.empty-state {
  background: #ffffff;
  border: 1px solid #dce1db;
  border-radius: 8px;
}

.metric {
  padding: 14px 16px;
}

.metric span,
.empty-line {
  color: #5e6f69;
}

.metric strong {
  display: block;
  font-size: 1.1rem;
  margin-top: 4px;
}

.panel {
  padding: 18px;
  overflow-x: auto;
}

.empty-state {
  margin-top: 24px;
  padding: 28px;
}

.empty-state p,
.empty-line {
  margin: 0;
}

.fencer-list {
  display: grid;
  gap: 10px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.fencer-list li {
  align-items: center;
  border-bottom: 1px solid #edf0ec;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 0 0 10px;
}

.fencer-list strong,
.fencer-list span,
.rank-stack span {
  display: block;
}

.fencer-list span,
.rank-stack {
  color: #5e6f69;
  font-size: 0.9rem;
}

.rank-stack {
  text-align: right;
  min-width: 96px;
}

.medal-summary {
  display: grid;
  gap: 10px;
}

.medal-summary strong {
  font-size: 1.35rem;
}

.medal-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.medal-row span {
  background: #f4efe3;
  border-radius: 999px;
  color: #5f4b16;
  padding: 6px 10px;
}

table {
  border-collapse: collapse;
  width: 100%;
}

th,
td {
  border-bottom: 1px solid #edf0ec;
  padding: 10px 8px;
  text-align: left;
  white-space: nowrap;
}

th {
  color: #52635f;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
}

.bar-chart,
.split-chart {
  display: grid;
  gap: 12px;
}

.bar-row,
.split-row {
  align-items: center;
  display: grid;
  gap: 10px;
}

.bar-row {
  grid-template-columns: 72px 1fr 48px;
}

.split-row {
  grid-template-columns: 64px 80px 1fr 44px;
}

.bar-track {
  background: #edf0ec;
  border-radius: 999px;
  height: 14px;
  overflow: hidden;
}

.bar-fill {
  border-radius: inherit;
  height: 100%;
}

.bar-green {
  background: #2d8b67;
}

.bar-gold {
  background: #c6922c;
}

.bar-red {
  background: #ba4d48;
}

.bar-blue {
  background: #3e6f9f;
}

@media (max-width: 860px) {
  .federation-page {
    padding: 20px;
  }

  .hero {
    align-items: stretch;
    flex-direction: column;
  }

  .hero-metrics,
  .overview-grid,
  .analytics-grid {
    grid-template-columns: 1fr;
  }

  .split-row {
    grid-template-columns: 56px 72px 1fr 36px;
  }
}
`;
