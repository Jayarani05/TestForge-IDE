import { expect, test, type Page } from "@playwright/test";

async function openPanel(page: Page) {
  await page.goto("/tests/ai-panel.html");
  await expect(page.getByText("TESTFORGE AI", { exact: true })).toBeVisible();
}

function explainResponse(content: string) {
  return {
    task: "explain_code",
    provider: "mock",
    model: "test-model",
    content,
    input_tokens: 3,
    output_tokens: 5,
  };
}

test("explain code uses the current file when no selection exists", async ({ page }) => {
  let requestBody: Record<string, unknown> | undefined;

  await page.route("**/agents/execute", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(explainResponse("This file defines create_order.")),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open test fixture" }).click();

  await page.getByRole("button", { name: "Explain Code" }).first().click();

  await expect(
    page.getByText("This file defines create_order."),
  ).toBeVisible();
  expect(requestBody).toMatchObject({
    task: "explain_code",
    context: "def test_order():\n    assert True\n",
  });
});

test("explain code can explain selected code", async ({ page }) => {
  let requestBody: Record<string, unknown> | undefined;

  await page.route("**/agents/execute", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(explainResponse("Selected code explained.")),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open test fixture" }).click();

  const editor = page.locator(".monaco-editor").first();
  await editor.click();
  await page.keyboard.press("Control+A");

  await page.getByRole("button", { name: "Explain Code" }).first().click();

  await expect(page.getByText("Selected code explained.")).toBeVisible();
  expect(requestBody?.context).toContain("def test_order");
});

test("explain code handles an empty editor", async ({ page }) => {
  let requestCount = 0;

  await page.route("**/agents/execute", async (route) => {
    requestCount += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(explainResponse("unused")),
    });
  });

  await openPanel(page);

  await page.getByRole("button", { name: "Explain Code" }).first().click();

  await expect(
    page.getByText("No code is available to explain."),
  ).toBeVisible();
  expect(requestCount).toBe(0);
});

test("explain code displays API errors", async ({ page }) => {
  await page.route("**/agents/execute", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Provider unavailable" }),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open test fixture" }).click();

  await page.getByRole("button", { name: "Explain Code" }).first().click();

  await expect(page.getByText(/Provider unavailable/)).toBeVisible();
});

test("explain code does not modify source code", async ({ page }) => {
  await page.route("**/agents/execute", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(explainResponse("Explanation only.")),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open test fixture" }).click();

  const before = await page.evaluate(() => window.testforgeActiveEditorTab()?.content);

  await page.getByRole("button", { name: "Explain Code" }).first().click();
  await expect(page.getByText("Explanation only.")).toBeVisible();

  const after = await page.evaluate(() => window.testforgeActiveEditorTab()?.content);
  expect(after).toBe(before);
});