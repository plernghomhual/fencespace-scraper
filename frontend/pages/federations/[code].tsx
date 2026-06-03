import type { GetServerSideProps, InferGetServerSidePropsType } from "next";

import FederationOverview, {
  getFederationCountry,
  sanitizeFederationPageData,
  type FederationOverviewData,
  type FederationCountry,
} from "../../components/FederationOverview";

type FederationPageProps = {
  data: FederationOverviewData;
  preferTables: boolean;
};

const PUBLIC_SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const PUBLIC_SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export default function FederationPage({ data, preferTables }: InferGetServerSidePropsType<typeof getServerSideProps>) {
  return <FederationOverview data={data} preferTables={preferTables} />;
}

export const getServerSideProps: GetServerSideProps<FederationPageProps> = async (context) => {
  const codeParam = Array.isArray(context.params?.code) ? context.params?.code[0] : context.params?.code;
  const country = await resolveFederationCountry(codeParam);

  if (!country) {
    return { notFound: true };
  }

  const data = await loadFederationOverview(country);
  const preferTables = context.query.view === "table" || context.query.charts === "off";

  return {
    props: {
      data,
      preferTables,
    },
  };
};

async function resolveFederationCountry(code: string | undefined): Promise<FederationCountry | null> {
  return (await fetchCountryCode(code)) ?? getFederationCountry(code);
}

async function fetchCountryCode(code: string | undefined): Promise<FederationCountry | null> {
  const normalized = normalizeRouteCode(code);
  if (!normalized) {
    return null;
  }

  const rows = await fetchPublicRows("fs_country_codes", {
    select: "alpha3,alpha2,name,flag_emoji,olympic_code,fie_code,aliases",
    or: `(alpha3.eq.${normalized},alpha2.eq.${normalized},olympic_code.eq.${normalized},fie_code.eq.${normalized})`,
    limit: "1",
  });
  const row = rows[0] && typeof rows[0] === "object" ? (rows[0] as Record<string, unknown>) : null;
  const alpha3 = textValue(row?.alpha3);
  const name = textValue(row?.name);
  if (!row || !alpha3 || !name) {
    return null;
  }
  const aliases = row.aliases;

  return {
    alpha3,
    alpha2: textValue(row?.alpha2) ?? undefined,
    olympicCode: textValue(row?.olympic_code) ?? undefined,
    fieCode: textValue(row?.fie_code) ?? undefined,
    name,
    flag: textValue(row?.flag_emoji) ?? undefined,
    aliases: Array.isArray(aliases) ? aliases.map(textValue).filter((item): item is string => Boolean(item)) : [],
  };
}

async function loadFederationOverview(country: FederationCountry): Promise<FederationOverviewData> {
  const countryFilter = `in.(${countryQueryCodes(country).join(",")})`;
  const [topFencers, depthRows, medalRows, clubRows, nationalRankingRows, recentTournaments] = await Promise.all([
    fetchPublicRows("fs_fencers", {
      select: "id,name,country,weapon,category,world_rank,domestic_rank,club,fie_points",
      country: countryFilter,
      order: "world_rank.asc.nullslast",
      limit: "10",
    }),
    fetchPublicRows("fs_country_depth", {
      select: "country,weapon,category,fencers_in_top16,fencers_in_top32,fencers_in_top64,total_ranked,avg_world_rank",
      country: countryFilter,
      order: "fencers_in_top64.desc",
      limit: "100",
    }),
    fetchPublicRows("fs_medal_tables", {
      select: "scope,country,tier,gold,silver,bronze,total",
      country: countryFilter,
      scope: "in.(country,tier_country)",
      order: "total.desc",
      limit: "20",
    }),
    fetchPublicRows("fs_club_rankings", {
      select: "club,country,weapon,total_fencers,avg_rank,total_points",
      country: countryFilter,
      order: "total_points.desc",
      limit: "12",
    }),
    fetchPublicRows("fs_country_rankings", {
      select: "country,weapon,category,fencer_count,top8_count",
      country: countryFilter,
      order: "fencer_count.desc",
      limit: "100",
    }),
    fetchPublicRows("fs_tournaments", {
      select: "id,name,country,weapon,category,type,start_date,end_date",
      country: countryFilter,
      order: "start_date.desc.nullslast",
      limit: "10",
    }),
  ]);

  return sanitizeFederationPageData({
    federation: {
      code: country.alpha3,
      name: country.name,
      flag: country.flag,
    },
    topFencers,
    depthRows,
    medalRows,
    clubRows,
    nationalRankingRows,
    recentTournaments,
  });
}

function countryQueryCodes(country: FederationCountry): string[] {
  return [...new Set([country.alpha3, country.olympicCode, country.fieCode].filter((code): code is string => Boolean(code)))];
}

function normalizeRouteCode(code: string | undefined): string | null {
  const normalized = String(code ?? "")
    .trim()
    .replace(/[^A-Za-z0-9]/g, "")
    .toUpperCase();
  return normalized || null;
}

function textValue(value: unknown): string | null {
  if (typeof value !== "string" && typeof value !== "number") {
    return null;
  }
  const text = String(value).trim();
  return text || null;
}

async function fetchPublicRows(table: string, params: Record<string, string>): Promise<unknown[]> {
  if (!PUBLIC_SUPABASE_URL || !PUBLIC_SUPABASE_ANON_KEY) {
    return [];
  }

  const url = new URL(`/rest/v1/${table}`, PUBLIC_SUPABASE_URL);
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }

  try {
    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${PUBLIC_SUPABASE_ANON_KEY}`,
        apikey: PUBLIC_SUPABASE_ANON_KEY,
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      return [];
    }

    const data = await response.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}
