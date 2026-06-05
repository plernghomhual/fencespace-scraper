import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, test, vi } from "vitest";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const overlaySource = readFileSync(path.resolve(__dirname, "../obs-overlay/overlay.js"), "utf8");

function mountOverlayDom() {
  document.body.innerHTML = `
    <span id="overlay-status"></span>
    <h1 id="event-name"></h1>
    <p id="event-meta"></p>
    <time id="updated-at"></time>
    <section id="score-strip"></section>
    <ol id="leaderboard"></ol>
    <section id="bouts"></section>
  `;
}

describe("OBS overlay rendering", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  test("renders hostile live data as text and does not forward URL tokens", async () => {
    mountOverlayDom();
    window.history.pushState({}, "", "/obs-overlay/?tournament_id=t-1&token=secret-token&refresh=2000");
    Object.defineProperty(window, "setInterval", {
      configurable: true,
      value: vi.fn(),
    });

    const fetchMock = vi.fn<(input: RequestInfo | URL) => Promise<Response>>(async () => ({
      ok: true,
      json: async () => ({
        status: "active",
        active: true,
        updated_at: "2026-06-04T12:00:00Z",
        event: {
          name: '<img src=x onerror="alert(1)">',
          weapon: "<script>alert(2)</script>",
          gender: "Women",
          category: "Senior",
          country: "USA",
        },
        leaders: [{ rank: 1, name: '<svg onload="alert(3)">', country: "ITA" }],
        bouts: [
          {
            round: '<iframe src="javascript:alert(4)"></iframe>',
            status: '<b onclick="alert(5)">live</b>',
            fencer_a: { name: '<img src=x onerror="alert(6)">' },
            fencer_b: { name: "<script>alert(7)</script>" },
            score: { a: 15, b: 14 },
          },
        ],
      }),
    }) as Response);
    vi.stubGlobal("fetch", fetchMock);

    window.eval(overlaySource);

    await vi.waitFor(() => expect(document.body.textContent).toContain('<img src=x onerror="alert(1)">'));
    const firstFetch = fetchMock.mock.calls[0];
    if (!firstFetch) {
      throw new Error("expected overlay fetch to run");
    }
    const fetchedUrl = String(firstFetch[0]);

    expect(fetchedUrl).toContain("tournament_id=t-1");
    expect(fetchedUrl).not.toContain("token=");
    expect(document.querySelector("img,script,svg,iframe")).toBeNull();
    expect(document.querySelector("[onerror],[onload],[onclick]")).toBeNull();
    expect(document.body.textContent).toContain("<script>alert(7)</script>");
  });
});
