export type RawBracketRow = Record<string, unknown>;

export type BracketSide = {
  id: string | null;
  name: string;
  seed: number | null;
  score: number | null;
  isWinner: boolean;
  isBye: boolean;
};

export type BracketBoutStatus = "complete" | "bye" | "incomplete";

export type BracketBout = {
  id: string;
  roundName: string;
  roundOrder: number;
  boutOrder: number;
  sourceIndex: number;
  winnerId: string | null;
  sides: [BracketSide, BracketSide];
  status: BracketBoutStatus;
};

export type BracketRound = {
  id: string;
  name: string;
  order: number;
  bouts: BracketBout[];
};

export type NormalizedBracket = {
  rounds: BracketRound[];
  totalBouts: number;
};

const ROUND_KEYS = ["round_name", "roundName", "round", "stage", "phase"];
const ROUND_ORDER_KEYS = ["round_order", "roundOrder", "round_index", "roundIndex"];
const BOUT_ORDER_KEYS = [
  "bout_order",
  "boutOrder",
  "match_order",
  "matchOrder",
  "order",
  "position",
];
const WINNER_KEYS = ["winner_id", "winnerId", "winner", "winner_fencer_id"];
const WINNER_SIDE_A_VALUES = new Set(["a", "1", "left", "fencer_a", "fencera", "fencer1"]);
const WINNER_SIDE_B_VALUES = new Set(["b", "2", "right", "fencer_b", "fencerb", "fencer2"]);
const ROW_BYE_KEYS = ["is_bye", "isBye", "bye", "has_bye", "hasBye"];

const SIDE_KEYS = {
  a: {
    object: ["fencer_a", "fencerA", "fencer1", "a"],
    id: [
      "fencer_a_id",
      "fencerAId",
      "fencer1_id",
      "fencer1Id",
      "a_id",
      "fie_fencer_id_a",
    ],
    name: [
      "fencer_a_name",
      "fencerAName",
      "fencer1_name",
      "fencer1Name",
      "name_a",
      "athlete_a_name",
      "a_name",
    ],
    seed: ["seed_a", "seedA", "fencer_a_seed", "fencerASeed", "seed1", "a_seed"],
    score: ["score_a", "scoreA", "fencer_a_score", "fencerAScore", "score1", "a_score"],
    bye: ["fencer_a_bye", "fencerABye", "is_bye_a", "isByeA", "bye_a", "byeA"],
  },
  b: {
    object: ["fencer_b", "fencerB", "fencer2", "b"],
    id: [
      "fencer_b_id",
      "fencerBId",
      "fencer2_id",
      "fencer2Id",
      "b_id",
      "fie_fencer_id_b",
    ],
    name: [
      "fencer_b_name",
      "fencerBName",
      "fencer2_name",
      "fencer2Name",
      "name_b",
      "athlete_b_name",
      "b_name",
    ],
    seed: ["seed_b", "seedB", "fencer_b_seed", "fencerBSeed", "seed2", "b_seed"],
    score: ["score_b", "scoreB", "fencer_b_score", "fencerBScore", "score2", "b_score"],
    bye: ["fencer_b_bye", "fencerBBye", "is_bye_b", "isByeB", "bye_b", "byeB"],
  },
} as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readValue(row: RawBracketRow, keys: readonly string[]): unknown {
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(row, key)) {
      return row[key];
    }
  }

  const metadata = row.metadata;
  if (isRecord(metadata)) {
    for (const key of keys) {
      if (Object.prototype.hasOwnProperty.call(metadata, key)) {
        return metadata[key];
      }
    }
  }

  return undefined;
}

function readObject(row: RawBracketRow, keys: readonly string[]): Record<string, unknown> | null {
  const value = readValue(row, keys);
  return isRecord(value) ? value : null;
}

function toText(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  const text = String(value).trim();
  return text ? text : null;
}

function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  const parsed = Number(String(value).trim());
  return Number.isFinite(parsed) ? parsed : null;
}

function toBoolean(value: unknown): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    return value !== 0;
  }
  if (typeof value === "string") {
    return ["1", "true", "yes", "y", "bye"].includes(value.trim().toLowerCase());
  }
  return false;
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function inferRoundOrder(roundName: string): number {
  const lower = roundName.toLowerCase();
  const tableMatch = lower.match(/(?:table|round)\s+of\s+(\d+)/);

  if (tableMatch) {
    return 1000 - Number(tableMatch[1]);
  }
  if (lower.includes("quarter")) {
    return 992;
  }
  if (lower.includes("semi")) {
    return 996;
  }
  if (lower.includes("final")) {
    return 999;
  }
  return Number.MAX_SAFE_INTEGER;
}

function readSideValue(
  row: RawBracketRow,
  sideObject: Record<string, unknown> | null,
  directKeys: readonly string[],
  objectKeys: readonly string[],
): unknown {
  const direct = readValue(row, directKeys);
  if (direct !== undefined && direct !== null && direct !== "") {
    return direct;
  }
  if (!sideObject) {
    return undefined;
  }
  for (const key of objectKeys) {
    if (Object.prototype.hasOwnProperty.call(sideObject, key)) {
      return sideObject[key];
    }
  }
  return undefined;
}

function normalizeSide(
  row: RawBracketRow,
  side: "a" | "b",
  rowHasBye: boolean,
  otherHasCompetitor: boolean,
): Omit<BracketSide, "isWinner"> & { hasCompetitor: boolean } {
  const keys = SIDE_KEYS[side];
  const sideObject = readObject(row, keys.object);
  const idFromObject = readSideValue(row, sideObject, keys.object, [
    "id",
    "fencerId",
    "fencer_id",
    "fie_id",
  ]);
  const id = toText(readSideValue(row, sideObject, keys.id, ["id", "fencerId", "fencer_id"])) ??
    toText(idFromObject);
  const name = toText(
    readSideValue(row, sideObject, keys.name, ["name", "display_name", "full_name", "fullName"]),
  );
  const seed = toNumber(readSideValue(row, sideObject, keys.seed, ["seed", "initial_seed"]));
  const score = toNumber(readSideValue(row, sideObject, keys.score, ["score", "touches"]));
  const explicitBye = toBoolean(readSideValue(row, sideObject, keys.bye, ["isBye", "bye"]));
  const hasCompetitor = Boolean(id || name);
  const isBye = explicitBye || (rowHasBye && !hasCompetitor && otherHasCompetitor);

  return {
    id,
    name: isBye ? "BYE" : name ?? id ?? "TBD",
    seed,
    score,
    isBye,
    hasCompetitor,
  };
}

function inferWinnerId(sideA: BracketSide, sideB: BracketSide): string | null {
  const sideAIdentity = sideIdentity(sideA);
  const sideBIdentity = sideIdentity(sideB);

  if (sideA.isBye && sideBIdentity) {
    return sideBIdentity;
  }
  if (sideB.isBye && sideAIdentity) {
    return sideAIdentity;
  }
  if (sideA.score === null || sideB.score === null || sideA.score === sideB.score) {
    return null;
  }
  return sideA.score > sideB.score ? sideAIdentity : sideBIdentity;
}

function sideIdentity(side: BracketSide): string | null {
  if (side.id) {
    return side.id;
  }
  if (!side.isBye && side.name !== "TBD") {
    return side.name;
  }
  return null;
}

function winnerMatches(side: BracketSide, winnerId: string | null): boolean {
  if (!winnerId || side.isBye) {
    return false;
  }
  return side.id === winnerId || side.name === winnerId;
}

function sideHasCompetitor(
  row: RawBracketRow,
  sideObject: Record<string, unknown> | null,
  side: "a" | "b",
): boolean {
  const keys = SIDE_KEYS[side];
  return Boolean(
    toText(readValue(row, keys.id)) ||
      toText(readValue(row, keys.name)) ||
      toText(readValue(row, keys.object)) ||
      (sideObject && (toText(sideObject.id) || toText(sideObject.name))),
  );
}

function normalizeWinnerId(
  rawWinner: string | null,
  sideA: BracketSide,
  sideB: BracketSide,
): string | null {
  if (!rawWinner) {
    return null;
  }
  const normalized = rawWinner.toLowerCase().replace(/[^a-z0-9_]+/g, "");
  if (WINNER_SIDE_A_VALUES.has(normalized)) {
    return sideIdentity({ ...sideA, isWinner: false });
  }
  if (WINNER_SIDE_B_VALUES.has(normalized)) {
    return sideIdentity({ ...sideB, isWinner: false });
  }
  return rawWinner;
}

function normalizeBout(row: RawBracketRow, sourceIndex: number): BracketBout {
  const roundName = toText(readValue(row, ROUND_KEYS)) ?? "Direct Elimination";
  const roundOrder = toNumber(readValue(row, ROUND_ORDER_KEYS)) ?? inferRoundOrder(roundName);
  const boutOrder = toNumber(readValue(row, BOUT_ORDER_KEYS)) ?? sourceIndex + 1;
  const rowHasBye = toBoolean(readValue(row, ROW_BYE_KEYS)) ||
    (toText(readValue(row, ["status", "state"])) ?? "").toLowerCase() === "bye";

  const sideAObject = readObject(row, SIDE_KEYS.a.object);
  const sideBObject = readObject(row, SIDE_KEYS.b.object);
  const sideAHasCompetitor = sideHasCompetitor(row, sideAObject, "a");
  const sideBHasCompetitor = sideHasCompetitor(row, sideBObject, "b");

  const sideABase = normalizeSide(row, "a", rowHasBye, sideBHasCompetitor);
  const sideBBase = normalizeSide(row, "b", rowHasBye, sideAHasCompetitor);
  const explicitWinnerId = normalizeWinnerId(
    toText(readValue(row, WINNER_KEYS)),
    { ...sideABase, isWinner: false },
    { ...sideBBase, isWinner: false },
  );
  const inferredWinnerId = explicitWinnerId ??
    inferWinnerId({ ...sideABase, isWinner: false }, { ...sideBBase, isWinner: false });

  const sideA: BracketSide = {
    ...sideABase,
    isWinner: winnerMatches({ ...sideABase, isWinner: false }, inferredWinnerId),
  };
  const sideB: BracketSide = {
    ...sideBBase,
    isWinner: winnerMatches({ ...sideBBase, isWinner: false }, inferredWinnerId),
  };
  const status: BracketBoutStatus = sideA.isBye || sideB.isBye
    ? "bye"
    : sideA.isWinner || sideB.isWinner || (sideA.score !== null && sideB.score !== null)
      ? "complete"
      : "incomplete";

  return {
    id: toText(readValue(row, ["id", "bracket_id", "bout_id", "source_key"])) ??
      `${slugify(roundName) || "round"}-${boutOrder}-${sourceIndex}`,
    roundName,
    roundOrder,
    boutOrder,
    sourceIndex,
    winnerId: inferredWinnerId,
    sides: [sideA, sideB],
    status,
  };
}

export function normalizeBracket(rows: RawBracketRow[] | null | undefined): NormalizedBracket {
  const grouped = new Map<string, { name: string; order: number; firstIndex: number; bouts: BracketBout[] }>();

  for (const [sourceIndex, row] of (rows ?? []).entries()) {
    if (!isRecord(row)) {
      continue;
    }
    const bout = normalizeBout(row, sourceIndex);
    const roundKey = `${bout.roundOrder}:${bout.roundName}`;
    const existing = grouped.get(roundKey);
    if (existing) {
      existing.bouts.push(bout);
    } else {
      grouped.set(roundKey, {
        name: bout.roundName,
        order: bout.roundOrder,
        firstIndex: sourceIndex,
        bouts: [bout],
      });
    }
  }

  const rounds = Array.from(grouped.entries())
    .map(([key, round]) => ({
      id: slugify(key) || `round-${round.firstIndex}`,
      name: round.name,
      order: round.order,
      bouts: round.bouts.sort(
        (left, right) => left.boutOrder - right.boutOrder || left.sourceIndex - right.sourceIndex,
      ),
    }))
    .sort((left, right) => left.order - right.order);

  return {
    rounds,
    totalBouts: rounds.reduce((total, round) => total + round.bouts.length, 0),
  };
}
