import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";

import H2HComparison, {
  HeadToHeadApiResponse,
  isHeadToHeadApiResponse,
} from "../components/H2HComparison";
import HeadToHeadPage, { getServerSideProps } from "../pages/head-to-head";

const replace = vi.fn();
let routerQuery: Record<string, string | string[] | undefined> = {};

vi.mock("next/router", () => ({
  useRouter: () => ({
    isReady: true,
    pathname: "/head-to-head",
    query: routerQuery,
    replace,
  }),
}));

const fencers = {
  alex: {
    id: "00000000-0000-0000-0000-000000000001",
    name: "Alex Lee",
    country: "KOR",
    weapon: "Foil",
    category: "Senior",
    world_rank: 4,
  },
  jordan: {
    id: "00000000-0000-0000-0000-000000000002",
    name: "Jordan Park",
    country: "USA",
    weapon: "Foil",
    category: "Senior",
    world_rank: 7,
  },
  morgan: {
    id: "00000000-0000-0000-0000-000000000003",
    name: "Morgan Diaz",
    country: "ESP",
    weapon: "Epee",
    category: "Senior",
  },
};

const h2hPayload: HeadToHeadApiResponse = {
  fencer_a: fencers.alex.id,
  fencer_b: fencers.jordan.id,
  data: [
    {
      fencer_a_id: fencers.alex.id,
      fencer_b_id: fencers.jordan.id,
      weapon: "Foil",
      a_wins: 3,
      b_wins: 1,
      a_touches: 58,
      b_touches: 49,
      bouts_total: 4,
      last_meeting_date: "2026-05-18",
      last_winner_id: fencers.alex.id,
    },
    {
      fencer_a_id: fencers.alex.id,
      fencer_b_id: fencers.jordan.id,
      weapon: "Epee",
      a_wins: 2,
      b_wins: 2,
      a_touches: 20,
      b_touches: 30,
      bouts_total: 4,
      last_meeting_date: "2025-12-02",
      last_winner_id: fencers.jordan.id,
    },
  ],
};

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function installFetchMock(options: { h2h?: unknown; h2hStatus?: number; rejectH2H?: boolean } = {}) {
  const calls: string[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    calls.push(url);

    if (url.includes("/fencer/search")) {
      const parsed = new URL(url, "https://api.example.test");
      const name = (parsed.searchParams.get("name") || "").toLowerCase();
      const data = Object.values(fencers).filter((fencer) => fencer.name.toLowerCase().includes(name));
      return jsonResponse({ data, pagination: { limit: 8, offset: 0, count: data.length } });
    }

    if (url.includes(`/fencer/${fencers.alex.id}`)) {
      return jsonResponse({ profile: fencers.alex, social: [], equipment: [] });
    }

    if (url.includes(`/fencer/${fencers.jordan.id}`)) {
      return jsonResponse({ profile: fencers.jordan, social: [], equipment: [] });
    }

    if (url.includes(`/fencer/${fencers.morgan.id}`)) {
      return jsonResponse({ profile: fencers.morgan, social: [], equipment: [] });
    }

    if (url.includes("/fencer/missing-fencer")) {
      return jsonResponse({ detail: "Fencer not found" }, 404);
    }

    if (url.includes("/h2h/")) {
      if (options.rejectH2H) {
        throw new Error("network down");
      }
      return jsonResponse(options.h2h ?? h2hPayload, options.h2hStatus ?? 200);
    }

    throw new Error(`Unexpected fetch: ${url}`);
  });

  global.fetch = fetchMock as unknown as typeof fetch;
  return { calls, fetchMock };
}

async function searchAndSelect(label: string, searchText: string, optionName: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value: searchText } });
  const option = await screen.findByRole("option", { name: new RegExp(`select ${optionName}`, "i") });
  fireEvent.click(option);
}

describe("H2HComparison", () => {
  beforeEach(() => {
    vi.useRealTimers();
    routerQuery = {};
    replace.mockReset();
    installFetchMock();
  });

  test("selects two fencers and renders side-by-side H2H stats", async () => {
    const onSelectionChange = vi.fn();
    render(<H2HComparison debounceMs={0} onSelectionChange={onSelectionChange} />);

    await searchAndSelect("Fencer A", "alex", "Alex Lee");
    await searchAndSelect("Fencer B", "jordan", "Jordan Park");

    expect(await screen.findByText("Alex Lee vs Jordan Park")).toBeInTheDocument();

    const alexPanel = screen.getByTestId("left-fencer-stats");
    expect(within(alexPanel).getByText("5")).toBeInTheDocument();
    expect(within(alexPanel).getByText("3")).toBeInTheDocument();
    expect(within(alexPanel).getByText("78")).toBeInTheDocument();

    const jordanPanel = screen.getByTestId("right-fencer-stats");
    expect(within(jordanPanel).getByText("3")).toBeInTheDocument();
    expect(within(jordanPanel).getByText("5")).toBeInTheDocument();
    expect(within(jordanPanel).getByText("79")).toBeInTheDocument();

    expect(screen.getAllByText("Foil").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Epee").length).toBeGreaterThan(0);
    expect(screen.getAllByText("2026-05-18").length).toBeGreaterThan(0);
    expect(screen.getByText(/Alex Lee defeated Jordan Park/i)).toBeInTheDocument();
    expect(onSelectionChange).toHaveBeenLastCalledWith(fencers.alex.id, fencers.jordan.id);
  });

  test("blocks same-fencer comparison and keeps the H2H endpoint idle", async () => {
    const { calls } = installFetchMock();
    render(<H2HComparison debounceMs={0} />);

    await searchAndSelect("Fencer A", "alex", "Alex Lee");
    await searchAndSelect("Fencer B", "alex", "Alex Lee");

    expect(await screen.findByText("Choose two different fencers.")).toBeInTheDocument();
    expect(calls.some((url) => url.includes("/h2h/"))).toBe(false);
  });

  test("renders no-record and network-error states", async () => {
    installFetchMock({ h2h: { fencer_a: fencers.alex.id, fencer_b: fencers.morgan.id, data: [] } });
    const { rerender } = render(
      <H2HComparison debounceMs={0} initialFencerAId={fencers.alex.id} initialFencerBId={fencers.morgan.id} />
    );

    await waitFor(() => expect(screen.getByText("No head-to-head record yet.")).toBeInTheDocument());

    installFetchMock({ rejectH2H: true });
    rerender(<H2HComparison debounceMs={0} initialFencerAId={fencers.alex.id} initialFencerBId={fencers.jordan.id} />);

    expect(await screen.findByText("Could not load head-to-head data. Try again.")).toBeInTheDocument();
  });

  test("loads server-side H2H records from query param aliases", async () => {
    const response = await getServerSideProps({
      query: { a: fencers.alex.id, b: fencers.jordan.id },
    } as Parameters<typeof getServerSideProps>[0]);

    expect("props" in response ? response.props : null).toMatchObject({
      fencerA: fencers.alex.id,
      fencerB: fencers.jordan.id,
      result: { ok: true },
    });

    const props = "props" in response ? await response.props : null;
    render(<HeadToHeadPage {...props} />);

    expect(screen.getByRole("heading", { name: "Head-to-head" })).toBeInTheDocument();
    expect(screen.getByText("Epee")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  test("renders an empty state when no server-side H2H query is provided", async () => {
    const response = await getServerSideProps({
      query: {},
    } as Parameters<typeof getServerSideProps>[0]);

    const props = "props" in response ? await response.props : null;
    render(<HeadToHeadPage {...props} />);

    expect(screen.getByText("Enter two fencer IDs to load head-to-head records.")).toBeInTheDocument();
  });

  test("validates the H2H API response contract", () => {
    expect(isHeadToHeadApiResponse(h2hPayload)).toBe(true);
    expect(isHeadToHeadApiResponse({ fencer_a: fencers.alex.id, data: h2hPayload.data })).toBe(false);
    expect(isHeadToHeadApiResponse({ ...h2hPayload, data: [{ weapon: "Foil" }] })).toBe(false);
  });
});
