import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SRC_ROOT = path.resolve(__dirname, "../src");

function sourceFiles(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      return sourceFiles(fullPath);
    }
    return /\.(ts|tsx|js|jsx|css)$/.test(entry.name) ? [fullPath] : [];
  });
}

describe("browser bundle secret exposure guard", () => {
  it("does not reference private Supabase or scraper credentials in frontend source", () => {
    const forbidden = [
      "SUPABASE_" + "SERVICE_KEY",
      "SUPABASE_" + "KEY",
      "SCRAPER_" + "TOKEN",
      "SCRAPER_" + "PASSWORD"
    ];

    for (const file of sourceFiles(SRC_ROOT)) {
      const text = fs.readFileSync(file, "utf8");
      for (const token of forbidden) {
        expect(text, `${path.relative(SRC_ROOT, file)} exposes ${token}`).not.toContain(token);
      }
    }
  });
});
