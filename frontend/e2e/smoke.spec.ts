import { test, expect } from "@playwright/test";

// Live-stack smoke test for the three tabs the app actually ships now
// (Rohdaten / Zusammenhänge / Vorhersage). Requires the real backend (the
// launcher starts preview + backend).

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

test("raw data loads on start", async ({ page }) => {
  await expect(page.getByRole("heading", { name: "Rohdaten" })).toBeVisible();
  await expect(page.getByText(/Zeilen/).first()).toBeVisible({ timeout: 15_000 });
});

test("correlations heatmap loads and a pair can be opened", async ({ page }) => {
  await page.getByTestId("nav-correlations").click();
  await expect(page.getByTestId("corr-view")).toBeVisible({ timeout: 15_000 });
  await page.locator("td.heatmap-cell:not(.is-diag)").first().click();
  await expect(page.getByTestId("corr-pair")).toBeVisible({ timeout: 10_000 });
});

test("forecast fits on the seed dataset and reacts to the threshold slider", async ({
  page,
}) => {
  await page.getByTestId("nav-forecast").click();
  await expect(page.getByTestId("forecast-view")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("forecast-metrics")).toBeVisible();

  // shadcn/Radix slider: a focusable thumb driven by the keyboard, not an
  // <input type=range> that could be filled.
  const thumb = page
    .getByTestId("min-correlation-slider")
    .getByRole("slider");
  await thumb.focus();
  for (let i = 0; i < 10; i++) await thumb.press("ArrowRight");
  await expect(thumb).toHaveAttribute("aria-valuenow", "0.5");
  await expect(page.getByTestId("forecast-metrics")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("forecast-error")).toHaveCount(0);
});

test("specs synthesis generates a plausible series and re-fits live", async ({
  page,
}) => {
  await page.getByTestId("nav-forecast").click();
  await page.getByTestId("source-specs").click();
  await page.getByTestId("preset-50k-h100-training").click();
  await expect(page.getByTestId("specs-summary")).toContainText("50,000", {
    timeout: 15_000,
  });
  await expect(page.getByTestId("forecast-metrics")).toBeVisible();
});

test("a synthesized series can be saved as CSV and imported back", async ({
  page,
}) => {
  await page.getByTestId("nav-forecast").click();
  await page.getByTestId("source-specs").click();
  await page.getByTestId("preset-50k-h100-training").click();
  await expect(page.getByTestId("specs-summary")).toBeVisible({ timeout: 15_000 });

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("specs-download").click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/^rechenzentrum-.*\.csv$/);

  // Re-upload the downloaded bytes under their real filename (the temp path
  // Playwright stores them at has no .csv extension).
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(chunk as Buffer);

  await page.getByTestId("source-upload").click();
  await page.setInputFiles('[data-testid="specs-upload-input"]', {
    name: download.suggestedFilename(),
    mimeType: "text/csv",
    buffer: Buffer.concat(chunks),
  });
  await expect(page.getByTestId("upload-summary")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("forecast-error")).toHaveCount(0);
  // The facility-wide meter wins over the IT sub-meter, so a re-imported
  // synthesized series forecasts the same column as the live specs source.
  await expect(page.getByTestId("target-select")).toContainText(
    "Gesamt-Stromverbrauch (kW)"
  );
});

test("a CSV without the default target column still forecasts", async ({
  page,
}) => {
  // Columns the app has never seen: no it_stromverbrauch_kw anywhere.
  const rows = ["ts,gpu_util,facility_power_kw"];
  for (let i = 0; i < 120; i++) {
    rows.push(`2026-01-01T${String(i % 24).padStart(2, "0")}:00,${i % 100},${(i % 100) * 2.5 + 40}`);
  }

  await page.getByTestId("nav-forecast").click();
  await page.getByTestId("source-upload").click();
  await page.setInputFiles('[data-testid="specs-upload-input"]', {
    name: "fremd.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(rows.join("\n")),
  });

  await expect(page.getByTestId("upload-summary")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("forecast-error")).toHaveCount(0);
  // The power column wins over the utilisation column via the name hint.
  await expect(page.getByTestId("target-select")).toContainText(
    "facility power kw"
  );
});
