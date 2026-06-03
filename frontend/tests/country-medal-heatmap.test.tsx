import { fireEvent, render, screen, within } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";

import CountryMedalHeatmap from "../components/CountryMedalHeatmap";
import {
  normalizeCountryCode,
  normalizeCountryMedalRows,
} from "../lib/countryMap";

describe("country medal normalization", () => {
  it("normalizes alpha-2, alpha-3, country-name, and fencing code variants", () => {
    expect(normalizeCountryCode(" us ")).toBe("USA");
    expect(normalizeCountryCode("United States")).toBe("USA");
    expect(normalizeCountryCode("UK")).toBe("GBR");
    expect(normalizeCountryCode("deu")).toBe("GER");
    expect(normalizeCountryCode("  FIE neutral athlete ")).toBe("AIN");
  });

  it("aggregates duplicate country rows and preserves unknown country codes without coordinates", () => {
    const countries = normalizeCountryMedalRows([
      {
        country: "USA",
        gold: "1",
        silver: 2,
        bronze: 0,
        latitude: 38,
        longitude: -97,
      },
      {
        country_code: "us",
        country_name: "United States",
        gold: 0,
        silver: 1,
        bronze: 1,
        latitude: 999,
        longitude: -999,
      },
      {
        country_code: "ZZZ",
        country_name: "Unknown delegation",
        gold: 0,
        silver: 0,
        bronze: 1,
      },
    ]);

    const usa = countries.find((country) => country.code === "USA");
    const unknown = countries.find((country) => country.code === "ZZZ");

    expect(usa).toMatchObject({
      name: "United States",
      gold: 1,
      silver: 3,
      bronze: 1,
      total: 5,
      latitude: 38,
      longitude: -97,
      hasCoordinates: true,
    });
    expect(unknown).toMatchObject({
      name: "Unknown delegation",
      gold: 0,
      silver: 0,
      bronze: 1,
      total: 1,
      latitude: null,
      longitude: null,
      hasCoordinates: false,
    });
  });
});

describe("CountryMedalHeatmap", () => {
  it("renders coordinate-backed countries as interactive map markers with medal details", () => {
    render(
      createElement(CountryMedalHeatmap, {
        rows: [
          {
            country_code: "FRA",
            country_name: "France",
            gold: 2,
            silver: 1,
            bronze: 3,
            latitude: 46.2,
            longitude: 2.2,
          },
        ],
      }),
    );

    const marker = screen.getByLabelText(/france: 6 medals/i);
    fireEvent.click(marker);

    const dialog = screen.getByRole("dialog", { name: /france medal details/i });
    expect(within(dialog).getByText("France")).toBeInTheDocument();
    expect(within(dialog).getByText("Gold")).toBeInTheDocument();
    expect(within(dialog).getByText("2")).toBeInTheDocument();
    expect(within(dialog).getByText("Silver")).toBeInTheDocument();
    expect(within(dialog).getByText("1")).toBeInTheDocument();
    expect(within(dialog).getByText("Bronze")).toBeInTheDocument();
    expect(within(dialog).getByText("3")).toBeInTheDocument();
  });

  it("keeps countries without coordinates in the accessible fallback table and no-coordinate list", () => {
    render(
      createElement(CountryMedalHeatmap, {
        rows: [
          {
            country_code: "AIN",
            country_name: "Individual Neutral Athletes",
            gold: 1,
            silver: 0,
            bronze: 0,
            latitude: null,
            longitude: null,
          },
        ],
      }),
    );

    expect(screen.queryByLabelText(/individual neutral athletes/i)).toBeNull();
    const missing = screen.getByRole("region", { name: /countries without map coordinates/i });
    expect(missing).toBeInTheDocument();
    expect(within(missing).getByText(/individual neutral athletes/i)).toBeInTheDocument();

    const table = screen.getByRole("table", { name: /country medal totals/i });
    expect(within(table).getByRole("cell", { name: "AIN" })).toBeInTheDocument();
    expect(within(table).getAllByRole("cell", { name: "1" })).toHaveLength(2);
  });

  it("renders a stable empty state when no medal data is available", () => {
    render(createElement(CountryMedalHeatmap, { rows: [] }));

    expect(screen.getByText(/no country medal data available/i)).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: /country medal totals/i })).toBeNull();
  });
});
