export type MedalValue = number | string | null | undefined;

export type CountryMedalInputRow = {
  country?: string | null;
  nationality?: string | null;
  country_code?: string | null;
  countryCode?: string | null;
  country_name?: string | null;
  countryName?: string | null;
  name?: string | null;
  code?: string | null;
  alpha2?: string | null;
  alpha3?: string | null;
  iso2?: string | null;
  iso3?: string | null;
  noc?: string | null;
  olympic_code?: string | null;
  olympicCode?: string | null;
  fie_code?: string | null;
  fieCode?: string | null;
  gold?: MedalValue;
  silver?: MedalValue;
  bronze?: MedalValue;
  total?: MedalValue;
  latitude?: MedalValue;
  longitude?: MedalValue;
  lat?: MedalValue;
  lng?: MedalValue;
  lon?: MedalValue;
};

export type CountryMedalDatum = {
  code: string;
  name: string;
  gold: number;
  silver: number;
  bronze: number;
  total: number;
  latitude: number | null;
  longitude: number | null;
  hasCoordinates: boolean;
};

export type ProjectedCountryPoint = CountryMedalDatum & {
  x: number;
  y: number;
};

type CountryMetadata = {
  name: string;
  latitude: number | null;
  longitude: number | null;
};

const UNKNOWN_CODE = "UNK";

const COUNTRY_ALIASES: Record<string, string> = {
  AIN: "AIN",
  FIENEUTRALATHLETE: "AIN",
  FIEINDEPENDENTATHLETE: "AIN",
  INDIVIDUALNEUTRALATHLETE: "AIN",
  INDIVIDUALNEUTRALATHLETES: "AIN",
  NEUTRALATHLETE: "AIN",
  NEUTRALATHLETES: "AIN",
  US: "USA",
  USA: "USA",
  UNITEDSTATES: "USA",
  UNITEDSTATESOFAMERICA: "USA",
  AMERICA: "USA",
  GB: "GBR",
  GBR: "GBR",
  UK: "GBR",
  UNITEDKINGDOM: "GBR",
  GREATBRITAIN: "GBR",
  BRITAIN: "GBR",
  FR: "FRA",
  FRA: "FRA",
  FRANCE: "FRA",
  IT: "ITA",
  ITA: "ITA",
  ITALY: "ITA",
  DE: "GER",
  DEU: "GER",
  GER: "GER",
  GERMANY: "GER",
  RU: "RUS",
  RUS: "RUS",
  RUSSIA: "RUS",
  RUSSIANFEDERATION: "RUS",
  ROC: "ROC",
  RUSSIANOLYMPICCOMMITTEE: "ROC",
  UA: "UKR",
  UKR: "UKR",
  UKRAINE: "UKR",
  JP: "JPN",
  JPN: "JPN",
  JAPAN: "JPN",
  KR: "KOR",
  KOR: "KOR",
  KOREA: "KOR",
  SOUTHKOREA: "KOR",
  REPUBLICOFKOREA: "KOR",
  CN: "CHN",
  CHN: "CHN",
  CHINA: "CHN",
  CA: "CAN",
  CAN: "CAN",
  CANADA: "CAN",
  BR: "BRA",
  BRA: "BRA",
  BRAZIL: "BRA",
  PL: "POL",
  POL: "POL",
  POLAND: "POL",
  CH: "SUI",
  CHE: "SUI",
  SUI: "SUI",
  SWITZERLAND: "SUI",
  NL: "NED",
  NLD: "NED",
  NED: "NED",
  NETHERLANDS: "NED",
  HK: "HKG",
  HKG: "HKG",
  HONGKONG: "HKG",
  SG: "SGP",
  SGP: "SGP",
  SINGAPORE: "SGP",
  IL: "ISR",
  ISR: "ISR",
  ISRAEL: "ISR",
  EG: "EGY",
  EGY: "EGY",
  EGYPT: "EGY",
  NZ: "NZL",
  NZL: "NZL",
  NEWZEALAND: "NZL",
  AU: "AUS",
  AUS: "AUS",
  AUSTRALIA: "AUS",
  BE: "BEL",
  BEL: "BEL",
  BELGIUM: "BEL",
  HU: "HUN",
  HUN: "HUN",
  HUNGARY: "HUN",
  FI: "FIN",
  FIN: "FIN",
  FINLAND: "FIN",
  DK: "DEN",
  DNK: "DEN",
  DEN: "DEN",
  DENMARK: "DEN",
  AR: "ARG",
  ARG: "ARG",
  ARGENTINA: "ARG",
  TW: "TPE",
  TPE: "TPE",
  TAIWAN: "TPE",
  CHINESETAIPEI: "TPE",
  UNKNOWN: UNKNOWN_CODE,
  STATELESS: UNKNOWN_CODE,
  UNK: UNKNOWN_CODE,
};

const COUNTRY_METADATA: Record<string, CountryMetadata> = {
  AIN: { name: "Individual Neutral Athletes", latitude: null, longitude: null },
  ARG: { name: "Argentina", latitude: -34.0, longitude: -64.0 },
  AUS: { name: "Australia", latitude: -25.0, longitude: 133.0 },
  BEL: { name: "Belgium", latitude: 50.5, longitude: 4.5 },
  BRA: { name: "Brazil", latitude: -10.0, longitude: -55.0 },
  CAN: { name: "Canada", latitude: 56.0, longitude: -106.0 },
  CHN: { name: "China", latitude: 35.0, longitude: 103.0 },
  DEN: { name: "Denmark", latitude: 56.0, longitude: 10.0 },
  EGY: { name: "Egypt", latitude: 26.8, longitude: 30.8 },
  FIN: { name: "Finland", latitude: 64.0, longitude: 26.0 },
  FRA: { name: "France", latitude: 46.2, longitude: 2.2 },
  GBR: { name: "Great Britain", latitude: 54.0, longitude: -2.0 },
  GER: { name: "Germany", latitude: 51.0, longitude: 10.0 },
  HKG: { name: "Hong Kong", latitude: 22.3, longitude: 114.2 },
  HUN: { name: "Hungary", latitude: 47.0, longitude: 19.0 },
  ISR: { name: "Israel", latitude: 31.0, longitude: 35.0 },
  ITA: { name: "Italy", latitude: 42.8, longitude: 12.8 },
  JPN: { name: "Japan", latitude: 36.0, longitude: 138.0 },
  KOR: { name: "South Korea", latitude: 36.5, longitude: 127.8 },
  NED: { name: "Netherlands", latitude: 52.2, longitude: 5.3 },
  NZL: { name: "New Zealand", latitude: -41.0, longitude: 174.0 },
  POL: { name: "Poland", latitude: 52.0, longitude: 19.0 },
  ROC: { name: "Russian Olympic Committee", latitude: null, longitude: null },
  RUS: { name: "Russia", latitude: 61.5, longitude: 105.3 },
  SGP: { name: "Singapore", latitude: 1.35, longitude: 103.8 },
  SUI: { name: "Switzerland", latitude: 46.8, longitude: 8.2 },
  TPE: { name: "Chinese Taipei", latitude: 23.7, longitude: 121.0 },
  UKR: { name: "Ukraine", latitude: 49.0, longitude: 32.0 },
  USA: { name: "United States", latitude: 38.0, longitude: -97.0 },
};

const CODE_FIELDS: (keyof CountryMedalInputRow)[] = [
  "country_code",
  "countryCode",
  "code",
  "alpha3",
  "iso3",
  "noc",
  "olympic_code",
  "olympicCode",
  "fie_code",
  "fieCode",
  "alpha2",
  "iso2",
  "country",
  "nationality",
  "country_name",
  "countryName",
  "name",
];

const NAME_FIELDS: (keyof CountryMedalInputRow)[] = [
  "country_name",
  "countryName",
  "name",
  "country",
  "nationality",
];

function cleanText(value: unknown): string | null {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  return text || null;
}

function aliasKey(value: unknown): string | null {
  const text = cleanText(value);
  if (!text) {
    return null;
  }
  return text
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "")
    .toUpperCase();
}

function firstText(row: CountryMedalInputRow, fields: (keyof CountryMedalInputRow)[]): string | null {
  for (const field of fields) {
    const text = cleanText(row[field]);
    if (text) {
      return text;
    }
  }
  return null;
}

function readNumber(value: MedalValue): number {
  if (value === null || value === undefined || value === "") {
    return 0;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return 0;
  }
  return Math.trunc(parsed);
}

function readCoordinate(value: MedalValue, min: number, max: number): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) {
    return null;
  }
  return parsed;
}

function rowCoordinate(row: CountryMedalInputRow, fields: (keyof CountryMedalInputRow)[], min: number, max: number) {
  for (const field of fields) {
    const coordinate = readCoordinate(row[field], min, max);
    if (coordinate !== null) {
      return coordinate;
    }
  }
  return null;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function isBetterName(name: string): boolean {
  if (/^[a-z0-9]{2,4}$/i.test(name.replace(/\s+/g, ""))) {
    return false;
  }
  const key = aliasKey(name);
  return Boolean(key && !["UNK", "UNKNOWN", "STATELESS"].includes(key));
}

export function normalizeCountryCode(value: unknown): string | null {
  const key = aliasKey(value);
  if (!key) {
    return null;
  }
  if (COUNTRY_ALIASES[key]) {
    return COUNTRY_ALIASES[key];
  }
  if (/^[A-Z]{3}$/.test(key)) {
    return key;
  }
  if (/^[A-Z0-9]{2,4}$/.test(key)) {
    return key;
  }
  return null;
}

export function getCountryMetadata(code: string): CountryMetadata {
  return COUNTRY_METADATA[code] ?? {
    name: code === UNKNOWN_CODE ? "Unknown country" : code,
    latitude: null,
    longitude: null,
  };
}

export function normalizeCountryMedalRows(rows: readonly CountryMedalInputRow[]): CountryMedalDatum[] {
  const byCode = new Map<string, CountryMedalDatum>();

  for (const row of rows) {
    const code = normalizeCountryCode(firstText(row, CODE_FIELDS)) ?? UNKNOWN_CODE;
    const metadata = getCountryMetadata(code);
    const rowName = firstText(row, NAME_FIELDS);
    const name = rowName && isBetterName(rowName) ? rowName : metadata.name;
    const gold = readNumber(row.gold);
    const silver = readNumber(row.silver);
    const bronze = readNumber(row.bronze);
    const medalBreakdownTotal = gold + silver + bronze;
    const fallbackTotal = readNumber(row.total);
    const total = medalBreakdownTotal > 0 ? medalBreakdownTotal : fallbackTotal;

    if (total <= 0) {
      continue;
    }

    const rowLatitude = rowCoordinate(row, ["latitude", "lat"], -90, 90);
    const rowLongitude = rowCoordinate(row, ["longitude", "lng", "lon"], -180, 180);
    const latitude = rowLatitude ?? metadata.latitude;
    const longitude = rowLongitude ?? metadata.longitude;
    const hasCoordinates = latitude !== null && longitude !== null;
    const existing = byCode.get(code);

    if (!existing) {
      byCode.set(code, {
        code,
        name,
        gold,
        silver,
        bronze,
        total,
        latitude,
        longitude,
        hasCoordinates,
      });
      continue;
    }

    existing.gold += gold;
    existing.silver += silver;
    existing.bronze += bronze;
    existing.total += total;
    if (!isBetterName(existing.name) && isBetterName(name)) {
      existing.name = name;
    }
    if (!existing.hasCoordinates && hasCoordinates) {
      existing.latitude = latitude;
      existing.longitude = longitude;
      existing.hasCoordinates = true;
    }
  }

  return Array.from(byCode.values()).sort((left, right) => {
    if (right.total !== left.total) {
      return right.total - left.total;
    }
    return left.name.localeCompare(right.name);
  });
}

export function projectCountryPoint(country: CountryMedalDatum): ProjectedCountryPoint | null {
  if (!country.hasCoordinates || country.latitude === null || country.longitude === null) {
    return null;
  }

  return {
    ...country,
    x: clamp(((country.longitude + 180) / 360) * 100, 0, 100),
    y: clamp(((90 - country.latitude) / 180) * 100, 0, 100),
  };
}
