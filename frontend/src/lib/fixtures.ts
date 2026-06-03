import type {
  CountryDepth,
  Fencer,
  FencerProfile,
  HeadToHeadPayload,
  Ranking,
  Tournament,
  TournamentResult,
} from "@/lib/types";

export const fixtureFencers: Fencer[] = [
  {
    id: "f1",
    fie_id: "1001",
    name: "Alex Lee",
    country: "KOR",
    weapon: "Epee",
    category: "Senior",
    world_rank: 1,
    fie_points: 210.5,
  },
  {
    id: "f2",
    fie_id: "1002",
    name: "Mina Park",
    country: "KOR",
    weapon: "Foil",
    category: "Senior",
    world_rank: 8,
    fie_points: 128.25,
  },
  {
    id: "f3",
    fie_id: "1003",
    name: "Sam Stone",
    country: "USA",
    weapon: "Sabre",
    category: "Junior",
    world_rank: 19,
    fie_points: 77,
  },
];

export const fixtureTournaments: Tournament[] = [
  {
    id: "t1",
    fie_id: "9001",
    name: "Seoul Grand Prix",
    season: 2026,
    country: "KOR",
    weapon: "Epee",
    category: "Senior",
    type: "GP",
    start_date: "2026-05-02",
    end_date: "2026-05-04",
  },
  {
    id: "t2",
    fie_id: "9002",
    name: "Paris World Cup",
    season: 2026,
    country: "FRA",
    weapon: "Foil",
    category: "Senior",
    type: "WC",
    start_date: "2026-02-13",
    end_date: "2026-02-15",
  },
];

export const fixtureRankings: Ranking[] = [
  { season: 2026, weapon: "Epee", gender: "Men", category: "Senior", rank: 1, name: "Alex Lee", points: 210.5 },
  { season: 2026, weapon: "Foil", gender: "Women", category: "Senior", rank: 8, name: "Mina Park", points: 128.25 },
  { season: 2026, weapon: "Sabre", gender: "Men", category: "Junior", rank: 19, name: "Sam Stone", points: 77 },
];

export const fixtureTournamentResults: TournamentResult[] = [
  { tournament_id: "t1", fencer_id: "f1", rank: 1, name: "Alex Lee", nationality: "KOR" },
  { tournament_id: "t1", fencer_id: "f2", rank: 2, name: "Mina Park", nationality: "KOR" },
  { tournament_id: "t2", fencer_id: "f3", rank: 3, name: "Sam Stone", nationality: "USA" },
];

export const fixtureCountryDepth: CountryDepth[] = [
  {
    country: "KOR",
    weapon: "Epee",
    category: "Senior",
    fencers_in_top16: 3,
    fencers_in_top32: 7,
    fencers_in_top64: 12,
    total_ranked: 25,
    avg_world_rank: 22.4,
  },
  {
    country: "USA",
    weapon: "Sabre",
    category: "Junior",
    fencers_in_top16: 1,
    fencers_in_top32: 5,
    fencers_in_top64: 10,
    total_ranked: 31,
    avg_world_rank: 37.2,
  },
];

export const fixtureHeadToHead: HeadToHeadPayload = {
  fencer_a: "f1",
  fencer_b: "f2",
  data: [
    {
      fencer_a_id: "f1",
      fencer_b_id: "f2",
      weapon: "Epee",
      a_wins: 3,
      b_wins: 1,
      a_touches: 55,
      b_touches: 42,
      bouts_total: 4,
      last_meeting_date: "2026-05-04",
    },
  ],
};

export function fixtureProfile(id: string): FencerProfile | null {
  const profile = fixtureFencers.find((fencer) => fencer.id === id);
  if (!profile) {
    return null;
  }
  return {
    profile,
    career_stats: {
      total_competitions: profile.id === "f1" ? 12 : 4,
      best_world_rank: profile.world_rank,
      podiums: profile.id === "f1" ? 5 : 1,
    },
    social: [],
    equipment: [],
  };
}
