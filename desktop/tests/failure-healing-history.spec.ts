import { expect, test, type Page } from "@playwright/test";

async function openPanel(page: Page) {
  await page.goto("/tests/ai-panel.html");
  await expect(page.getByText("TESTFORGE AI", { exact: true })).toBeVisible();
}

function failureRecord(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    repository_path: "/test/repository",
    file_path: "tests/test_orders.py",
    failure_type: "assertion_failure",
    root_cause: "Expected 2 but received 3",
    severity: "high",
    suggested_fix: "Fix the assertion",
    repair_required: true,
    execution_id: "execution-1",
    observed_details: ["assert 2 == 3"],
    evidence: ["Observed assertion mismatch"],
    inferred_explanation: "The test likely expected a different value",
    recommendations: ["Update expected value"],
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function healingRecord(overrides: Record<string, unknown> = {}) {
  return {
    id: 2,
    repair_id: "repair-1",
    execution_id: "execution-1",
    failure_analysis_id: 1,
    repository_path: "/test/repository",
    file_path: "tests/test_orders.py",
    failure_type: "assertion_failure",
    status: "generated",
    explanation: "Repair candidate explanation",
    changes: "Changed assertion",
    original_code: "assert result == 2",
    proposed_code: "assert result == 3",
    review_status: "pending_review",
    apply_approved: null,
    apply_outcome: null,
    restore_outcome: null,
    applied_at: null,
    restored_at: null,
    created_at: "2026-01-02T00:00:00Z",
    ...overrides,
  };
}

test("failure and healing history loading state", async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });

  await page.route("**/history/failures*", async (route) => {
    await gate;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
  await page.route("**/history/self-healing*", async (route) => {
    await gate;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open history" }).click();

  await expect(
    page.getByText("Loading failure and healing history..."),
  ).toBeVisible();

  release();

  await expect(
    page.getByText("No failure or healing history is available."),
  ).toBeVisible();
});

test("empty failure and healing history", async ({ page }) => {
  await page.route("**/history/failures*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
  await page.route("**/history/self-healing*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open history" }).click();

  await expect(
    page.getByText("No failure or healing history is available."),
  ).toBeVisible();
});

test("populated failure history", async ({ page }) => {
  await page.route("**/history/failures*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([failureRecord()]),
    });
  });
  await page.route("**/history/self-healing*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open history" }).click();

  await expect(page.getByText("Failure record #1")).toBeVisible();
  await expect(page.getByText("Execution ID: execution-1")).toBeVisible();
  await expect(page.getByText("Failure ID: 1")).toBeVisible();
  await expect(page.getByText("Observed evidence", { exact: true })).toBeVisible();
  await expect(page.getByText("Observed assertion mismatch")).toBeVisible();
  await expect(
    page.getByText("Inferred explanation (not observed evidence)"),
  ).toBeVisible();
  await expect(
    page.getByText("The test likely expected a different value"),
  ).toBeVisible();
});
test("failure evidence is distinguished from inferred explanation", async ({ page }) => {
  await page.route("**/history/failures*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        failureRecord({
          evidence: ["Observed assertion mismatch"],
          inferred_explanation: "Inferred root cause",
        }),
      ]),
    });
  });
  await page.route("**/history/self-healing*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open history" }).click();

  await expect(page.getByText("Observed assertion mismatch")).toBeVisible();
  await expect(page.getByText("Inferred root cause")).toBeVisible();
});

test("populated healing history", async ({ page }) => {
  await page.route("**/history/failures*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
  await page.route("**/history/self-healing*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([healingRecord()]),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open history" }).click();

  await expect(page.getByText("Healing record #2")).toBeVisible();
  await expect(page.getByText("Healing record ID: 2")).toBeVisible();
  await expect(page.getByText("Repair ID: repair-1")).toBeVisible();
  await expect(page.getByText("Repair lifecycle status: generated")).toBeVisible();
  await expect(page.getByText("Review status: pending_review")).toBeVisible();
  await expect(page.getByText("Original versus proposed source")).toBeVisible();
  await expect(page.getByText("assert result == 2")).toBeVisible();
  await expect(page.getByText("assert result == 3")).toBeVisible();
});

test("repair lifecycle display", async ({ page }) => {
  await page.route("**/history/failures*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
  await page.route("**/history/self-healing*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        healingRecord({
          status: "applied",
          review_status: "applied",
          apply_outcome: "success",
          applied_at: "2026-01-03T00:00:00Z",
        }),
      ]),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open history" }).click();

  await expect(page.getByText("Repair lifecycle status: applied")).toBeVisible();
  await expect(page.getByText("Apply outcome: success")).toBeVisible();
  await expect(page.getByText("Applied at: 2026-01-03T00:00:00Z")).toBeVisible();
});

test("failure and healing history API error", async ({ page }) => {
  await page.route("**/history/failures*", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ detail: "History unavailable" }),
    });
  });
  await page.route("**/history/self-healing*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open history" }).click();

  await expect(page.getByText(/History unavailable/)).toBeVisible();
});

test("missing optional fields are handled", async ({ page }) => {
  await page.route("**/history/failures*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: 3,
          repository_path: "/test/repository",
          file_path: "tests/test_orders.py",
          failure_type: "assertion_failure",
          root_cause: null,
          severity: "medium",
          suggested_fix: "Fix it",
          repair_required: false,
          execution_id: null,
          observed_details: [],
          evidence: [],
          inferred_explanation: null,
          recommendations: [],
          created_at: "2026-01-04T00:00:00Z",
        },
      ]),
    });
  });
  await page.route("**/history/self-healing*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open history" }).click();

  await expect(page.getByText("Failure record #3")).toBeVisible();
  await expect(page.getByText("Execution ID: —")).toBeVisible();
  await expect(page.getByText("Inferred explanation (not observed evidence)")).toBeVisible();
});