export type SearchParams = Record<string, string | string[] | undefined>;

export type Pagination = {
  limit: number;
  offset: number;
  count: number;
};

export type DataSource = "live" | "mock";

export type ApiListResult<T> =
  | { ok: true; source: DataSource; data: T[]; pagination: Pagination }
  | { ok: false; source: DataSource; error: string; status?: number; data?: T[]; pagination?: Pagination };

export type ApiItemResult<T> =
  | { ok: true; source: DataSource; data: T }
  | { ok: false; source: DataSource; error: string; status?: number };

export type Fencer = {
  id: string;
  fie_id?: string | null;
  name?: string | null;
  country?: string | null;
  weapon?: string | null;
  category?: string | null;
  world_rank?: number | null;
  fie_points?: number | null;
  image_url?: string | null;
};

export type FencerProfile = {
  profile: Fencer;
  career_stats?: Record<string, unknown> | null;
  social: Array<Record<string, unknown>>;
  equipment: Array<Record<string, unknown>>;
};

export type Tournament = {
  id: string;
  fie_id?: string | null;
  season?: number | null;
  name?: string | null;
  country?: string | null;
  weapon?: string | null;
  category?: string | null;
  type?: string | null;
  start_date?: string | null;
  end_date?: string | null;
};

export type TournamentResult = {
  tournament_id?: string | null;
  fencer_id?: string | null;
  rank?: number | null;
  name?: string | null;
  nationality?: string | null;
};

export type Ranking = {
  season?: number | null;
  weapon?: string | null;
  gender?: string | null;
  category?: string | null;
  rank?: number | null;
  name?: string | null;
  points?: number | null;
};

export type HeadToHeadRecord = {
  fencer_a_id?: string | null;
  fencer_b_id?: string | null;
  weapon?: string | null;
  a_wins?: number | null;
  b_wins?: number | null;
  a_touches?: number | null;
  b_touches?: number | null;
  bouts_total?: number | null;
  last_meeting_date?: string | null;
};

export type HeadToHeadPayload = {
  fencer_a: string;
  fencer_b: string;
  data: HeadToHeadRecord[];
};

export type CountryDepth = {
  country?: string | null;
  weapon?: string | null;
  category?: string | null;
  fencers_in_top16?: number | null;
  fencers_in_top32?: number | null;
  fencers_in_top64?: number | null;
  total_ranked?: number | null;
  avg_world_rank?: number | null;
};
