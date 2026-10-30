import { expect, test, type Page } from "@playwright/test";

const actionEvent = "testforge:analyze-failure";
const registeredEvents = [
  "testforge:generate-tests",
  "testforge:analyze-failure",
  "testforge:self-heal",
  "testforge:analytics",
  "testforge:open-ai",
];

async function openPanel(
  page: Page,
) {
  await page.goto("/tests/ai-panel.html");
  await expect(page.getByText("TESTFORGE AI", { exact: true })).toBeVisible();
}

async function dispatchAction(
  page: Page,
) {
  await page.evaluate((eventName) => {
    window.dispatchEvent(new CustomEvent(eventName));
  }, actionEvent);
}

function successResponse(content: string) {
  return {
    task: "analyze_failure",
    provider: "mock",
    model: "test-model",
    content,
    input_tokens: 3,
    output_tokens: 5,
    analysis: null,
  };
}

function generatedScenario(title: string, testType = "integration") {
  return {
    repository_path: "/test/repository",
    total_tests: 1,
    test_cases: [
      {
        id: "TC-INT-001",
        title,
        description:
          "Verify the order service passes an order to the repository and returns the persisted result.",
        test_type: testType,
        priority: "high",
        preconditions: ["The order repository is configured."],
        steps: [
          "Submit an order to the service.",
          "Verify the service calls the repository with that order.",
        ],
        expected_result:
          "The repository stores the order and the service returns it.",
        target_file: "src/order_service.py",
        target_function: "create_order",
      },
    ],
  };
}

function executionResponse(
  overrides: Record<string, unknown> = {},
) {
  return {
    execution_id: "execution-1",
    repository_path: "/test/repository",
    file_path: "tests/test_orders.py",
    framework: "pytest",
    status: "passed",
    exit_code: 0,
    stdout: "1 passed",
    stderr: "",
    duration_seconds: 0.25,
    error: null,
    coverage_percent: null,
    coverage_covered_statements: null,
    coverage_total_statements: null,
    coverage_error: null,
    source_digest: null,
    ...overrides,
  };
}

test("persistent listener uses the latest committed handler after rerender", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;

  await page.route("**/agents/execute", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(successResponse("Latest handler response")),
    });
  });

  await openPanel(page);
  await page
    .getByRole("complementary")
    .filter({ hasText: "AI Provider" })
    .getByRole("combobox")
    .selectOption("GPT");
  await page.getByRole("button", { name: "Rerender harness" }).click();
  await dispatchAction(page);

  await expect(page.getByText("Latest handler response")).toBeVisible();
  expect(requestBody).toMatchObject({
    task: "analyze_failure",
    provider: "gpt",
    repository_path: "/test/repository",
  });
});

test("rapid duplicate events are serialized by the working lock", async ({
  page,
}) => {
  let releaseResponse!: () => void;
  const responseGate = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  let requestCount = 0;

  await page.route("**/agents/execute", async (route) => {
    requestCount += 1;
    await responseGate;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(successResponse("Single response")),
    });
  });

  await openPanel(page);
  await page.evaluate((eventName) => {
    window.dispatchEvent(new CustomEvent(eventName));
    window.dispatchEvent(new CustomEvent(eventName));
  }, actionEvent);
  await expect.poll(() => requestCount).toBe(1);

  releaseResponse();
  await expect(page.getByText("Single response")).toBeVisible();
  expect(requestCount).toBe(1);
});

test("failure releases the lock and a later action succeeds", async ({
  page,
}) => {
  let requestCount = 0;

  await page.route("**/agents/execute", async (route) => {
    requestCount += 1;
    if (requestCount === 1) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Provider unavailable" }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(successResponse("Recovered response")),
    });
  });

  await openPanel(page);
  await dispatchAction(page);
  await expect(page.getByText(/Provider unavailable/)).toBeVisible();
  await expect(page.getByText("Ready")).toBeVisible();

  await dispatchAction(page);
  await expect(page.getByText("Recovered response")).toBeVisible();
  expect(requestCount).toBe(2);
});

test("consecutive successful actions retain separate messages and response fields", async ({
  page,
}) => {
  const duplicateKeyWarnings: string[] = [];
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      /same key/i.test(message.text())
    ) {
      duplicateKeyWarnings.push(message.text());
    }
  });

  let requestCount = 0;
  await page.route("**/agents/execute", async (route) => {
    requestCount += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        successResponse(`Response ${requestCount}`),
      ),
    });
  });

  await openPanel(page);
  await dispatchAction(page);
  await expect(page.getByText("Response 1")).toBeVisible();
  await dispatchAction(page);
  await expect(page.getByText("Response 2")).toBeVisible();

  await expect(page.getByText("Provider: mock").first()).toBeVisible();
  await expect(page.getByText("Model: test-model").first()).toBeVisible();
  expect(
    await page
      .locator("aside div.justify-end")
      .filter({ hasText: "Analyze Failure" })
      .count(),
  ).toBe(2);
  expect(duplicateKeyWarnings).toEqual([]);
  expect(requestCount).toBe(2);
});

test("event listeners are removed when the panel unmounts", async ({
  page,
}) => {
  let requestCount = 0;
  await page.route("**/agents/execute", async (route) => {
    requestCount += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(successResponse("Unexpected response")),
    });
  });

  await openPanel(page);
  await expect
    .poll(() =>
      page.evaluate((eventNames) =>
        eventNames.map((eventName) =>
          window.testforgeListenerCount(eventName),
        ),
      registeredEvents),
    )
    .toEqual([1, 1, 1, 1, 1]);

  await page.getByRole("button", { name: "Unmount panel" }).click();
  await expect(
    page.getByText("TESTFORGE AI", { exact: true }),
  ).toHaveCount(0);
  await expect
    .poll(() =>
      page.evaluate((eventNames) =>
        eventNames.map((eventName) =>
          window.testforgeListenerCount(eventName),
        ),
      registeredEvents),
    )
    .toEqual([0, 0, 0, 0, 0]);
  await page.evaluate((eventNames) => {
    for (const eventName of eventNames) {
      window.dispatchEvent(new CustomEvent(eventName));
    }
  }, registeredEvents);

  expect(requestCount).toBe(0);
});

test("scenario type and count reach the integration generation API and cards", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  let releaseResponse!: () => void;
  const responseGate = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });

  await page.route("**/tests/generate", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await responseGate;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(generatedScenario("Service-to-repository integration")),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByLabel("Scenario type").selectOption("integration");
  await page.getByLabel("Test case count").selectOption("3");
  await page.getByRole("button", { name: "Generate Test Cases" }).click();

  await expect.poll(() => requestBody).toMatchObject({
    repository_path: "/test/repository",
    test_types: ["integration"],
    count: 3,
  });
  expect(requestBody?.prompt).toContain("interactions between evidenced components");
  await expect(
    page.getByRole("button", { name: "Generating scenarios..." }),
  ).toBeDisabled();

  releaseResponse();
  await expect(
    page.getByText("Service-to-repository integration"),
  ).toBeVisible();
  await expect(page.getByText("integration", { exact: true })).toBeVisible();
  await expect(page.getByText(/repository stores the order/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Generate Test Cases" }),
  ).toBeEnabled();
});

test("scenario count selector exposes the validated minimum and maximum", async ({
  page,
}) => {
  const counts: number[] = [];
  await page.route("**/tests/generate", async (route) => {
    const body = route.request().postDataJSON() as {
      count: number;
    };
    counts.push(body.count);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(generatedScenario(`Count ${body.count}`)),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  for (const count of ["1", "50"]) {
    await page.getByLabel("Test case count").selectOption(count);
    await page.getByRole("button", { name: "Generate Test Cases" }).click();
    await expect(page.getByText(`Count ${count}`)).toBeVisible();
    expect(counts[counts.length - 1]).toBe(Number(count));
  }
});

test("existing all-category generation remains the default", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  await page.route("**/tests/generate", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(generatedScenario("Default category scenario")),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await expect(page.getByLabel("Scenario type")).toHaveValue("all");
  await page.getByRole("button", { name: "Generate Test Cases" }).click();
  await expect(page.getByText("Default category scenario")).toBeVisible();

  expect(requestBody).toMatchObject({
    test_types: [
      "functional",
      "integration",
      "api",
      "regression",
      "boundary",
      "negative",
      "exception",
      "edge_case",
    ],
    count: 5,
  });
  expect(requestBody?.prompt).toContain("comprehensive repository-aware test scenarios");
});

test("scenario cards preserve step order and handle missing optional details", async ({
  page,
}) => {
  const response = {
    repository_path: "/test/repository",
    total_tests: 2,
    test_cases: [
      {
        ...generatedScenario("Complete exception card", "exception").test_cases[0],
        id: "TC-EXC-001",
        description: "A long description ".repeat(30),
        preconditions: ["Fixture is ready."],
        steps: ["First ordered step.", "Second ordered step."],
        expected_result: "The documented exception is propagated.",
      },
      {
        id: "TC-EDGE-001",
        title: "Minimal edge case card",
        description: "",
        test_type: "edge_case",
        priority: "low",
        expected_result: "",
      },
    ],
  };
  await page.route("**/tests/generate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(response),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByRole("button", { name: "Generate Test Cases" }).click();

  await expect(page.getByText("Complete exception card")).toBeVisible();
  await expect(page.getByText("Minimal edge case card")).toBeVisible();
  await expect(page.getByText("exception", { exact: true })).toBeVisible();
  await expect(page.getByText("edge_case", { exact: true })).toBeVisible();
  await expect(page.getByText("No description provided.")).toBeVisible();
  await expect(page.getByText("No expected result provided.")).toBeVisible();
  await expect(page.getByText("Preconditions", { exact: true })).toHaveCount(1);
  await expect(page.getByText("Steps", { exact: true })).toHaveCount(1);
  expect(await page.locator("ol li").allTextContents()).toEqual([
    "1.First ordered step.",
    "2.Second ordered step.",
  ]);
});

test("exception and edge-case scenario selections remain independent", async ({
  page,
}) => {
  const requestBodies: Record<string, unknown>[] = [];
  await page.route("**/tests/generate", async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    requestBodies.push(body);
    const selectedType = (body.test_types as string[])[0];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        generatedScenario(`${selectedType} selector scenario`, selectedType),
      ),
    });
  });

  for (const scenarioType of ["exception", "edge_case"]) {
    await openPanel(page);
    await page.getByRole("button", { name: "Tests", exact: true }).click();
    await page.getByLabel("Scenario type").selectOption(scenarioType);
    await page.getByRole("button", { name: "Generate Test Cases" }).click();
    await expect(
      page.getByText(`${scenarioType} selector scenario`),
    ).toBeVisible();
    const requestBody = requestBodies[requestBodies.length - 1];
    expect(requestBody).toMatchObject({
      repository_path: "/test/repository",
      test_types: [scenarioType],
      count: 5,
    });
    expect(requestBody.prompt).toContain(
      scenarioType === "exception"
        ? "exception types"
        : "unusual combinations",
    );
  }

  expect(requestBodies.map((request) => request.test_types)).toEqual([
    ["exception"],
    ["edge_case"],
  ]);
});

test("Exception and Edge-Case Tests cards start matching requests", async ({
  page,
}) => {
  const requestTypes: string[][] = [];
  await page.route("**/tests/generate", async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    const types = body.test_types as string[];
    requestTypes.push(types);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        generatedScenario(`${types[0]} card scenario`, types[0]),
      ),
    });
  });

  for (const [label, scenarioType] of [
    ["Exception Tests", "exception"],
    ["Edge-Case Tests", "edge_case"],
  ]) {
    await openPanel(page);
    await page.getByRole("button", { name: "Tests", exact: true }).click();
    await page.getByRole("button", { name: new RegExp(label) }).click();
    await expect(page.getByText(`${scenarioType} card scenario`)).toBeVisible();
    expect(requestTypes[requestTypes.length - 1]).toEqual([scenarioType]);
  }

  expect(requestTypes).toEqual([["exception"], ["edge_case"]]);
});

test("integration scenario card starts an integration-only request", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  await page.route("**/tests/generate", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(generatedScenario("Integration card scenario")),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByRole("button", { name: /Integration Tests/ }).click();

  await expect(page.getByText("Integration card scenario")).toBeVisible();
  expect(requestBody).toMatchObject({
    test_types: ["integration"],
    count: 5,
  });
});

test("API scenario type and count reach the API generation endpoint and render", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  await page.route("**/tests/generate", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        generatedScenario("POST /orders API contract", "api"),
      ),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByLabel("Scenario type").selectOption("api");
  await page.getByLabel("Test case count").selectOption("8");
  await page.getByRole("button", { name: "Generate Test Cases" }).click();

  await expect(page.getByText("POST /orders API contract")).toBeVisible();
  await expect(page.getByText("api", { exact: true })).toBeVisible();
  expect(requestBody).toMatchObject({
    repository_path: "/test/repository",
    test_types: ["api"],
    count: 8,
  });
  expect(requestBody?.prompt).toContain("actual endpoint paths and HTTP methods");
});

test("API scenario card starts an API-only request", async ({ page }) => {
  let requestBody: Record<string, unknown> | undefined;
  await page.route("**/tests/generate", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        generatedScenario("API card scenario", "api"),
      ),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByRole("button", { name: /API Test Scenarios/ }).click();

  await expect(page.getByText("API card scenario")).toBeVisible();
  expect(requestBody).toMatchObject({
    test_types: ["api"],
    count: 5,
  });
});

test("regression selection sends a bounded regression-only request and renders results", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  let releaseResponse!: () => void;
  const responseGate = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });

  await page.route("**/tests/generate", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await responseGate;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        generatedScenario("Preserve order creation behavior", "regression"),
      ),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByLabel("Scenario type").selectOption("regression");
  await page.getByLabel("Test case count").selectOption("8");
  await page.getByRole("button", { name: "Generate Test Cases" }).click();

  await expect.poll(() => requestBody).toMatchObject({
    repository_path: "/test/repository",
    test_types: ["regression"],
    count: 8,
  });
  expect(requestBody?.prompt).toContain("current repository code");
  expect(requestBody?.prompt).toContain("Git history");
  await expect(
    page.getByRole("button", { name: "Generating scenarios..." }),
  ).toBeDisabled();

  releaseResponse();
  await expect(
    page.getByText("Preserve order creation behavior"),
  ).toBeVisible();
  await expect(page.getByText("regression", { exact: true })).toBeVisible();
});

test("Regression Tests card starts a regression-only request", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  await page.route("**/tests/generate", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        generatedScenario("Regression card scenario", "regression"),
      ),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByRole("button", { name: /Regression Tests/ }).click();

  await expect(page.getByText("Regression card scenario")).toBeVisible();
  expect(requestBody).toMatchObject({
    repository_path: "/test/repository",
    test_types: ["regression"],
    count: 5,
  });
});

test("regression generation errors recover to the explicit empty state", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  let requestCount = 0;
  await page.route("**/tests/generate", async (route) => {
    requestCount += 1;
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    if (requestCount === 1) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Regression scenario service unavailable",
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        test_cases: [],
        total_tests: 0,
      }),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByLabel("Scenario type").selectOption("regression");
  await page.getByLabel("Test case count").selectOption("3");
  await page.getByRole("button", { name: "Generate Test Cases" }).click();

  await expect(
    page.getByText(/Regression scenario service unavailable/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Generate Test Cases" }),
  ).toBeEnabled();
  expect(requestBody).toMatchObject({
    repository_path: "/test/repository",
    test_types: ["regression"],
    count: 3,
  });

  await page.getByRole("button", { name: "Generate Test Cases" }).click();
  await expect(
    page.getByRole("status").getByText(
      "No scenarios were returned for this request.",
    ),
  ).toBeVisible();
  expect(requestCount).toBe(2);
  expect(requestBody).toMatchObject({
    test_types: ["regression"],
    count: 3,
  });
});

test("boundary selection sends a boundary-only request and renders scenarios", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  let releaseResponse!: () => void;
  const responseGate = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });

  await page.route("**/tests/generate", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await responseGate;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        generatedScenario("Count at documented maximum", "boundary"),
      ),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByLabel("Scenario type").selectOption("boundary");
  await page.getByLabel("Test case count").selectOption("10");
  await page.getByRole("button", { name: "Generate Test Cases" }).click();

  await expect.poll(() => requestBody).toMatchObject({
    repository_path: "/test/repository",
    test_types: ["boundary"],
    count: 10,
  });
  expect(requestBody?.prompt).toContain("explicit constraints");
  expect(requestBody?.prompt).toContain("below, at, and above");
  await expect(
    page.getByRole("button", { name: "Generating scenarios..." }),
  ).toBeDisabled();

  releaseResponse();
  await expect(
    page.getByText("Count at documented maximum"),
  ).toBeVisible();
  await expect(page.getByText("boundary", { exact: true })).toBeVisible();
});

test("Boundary Tests card starts a boundary-only request", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  await page.route("**/tests/generate", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        generatedScenario("Boundary card scenario", "boundary"),
      ),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByRole("button", { name: /Boundary Tests/ }).click();

  await expect(page.getByText("Boundary card scenario")).toBeVisible();
  expect(requestBody).toMatchObject({
    repository_path: "/test/repository",
    test_types: ["boundary"],
    count: 5,
  });
});

test("boundary generation errors recover to the explicit empty state", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  let requestCount = 0;
  await page.route("**/tests/generate", async (route) => {
    requestCount += 1;
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    if (requestCount === 1) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Boundary scenario service unavailable",
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        test_cases: [],
        total_tests: 0,
      }),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByLabel("Scenario type").selectOption("boundary");
  await page.getByLabel("Test case count").selectOption("3");
  await page.getByRole("button", { name: "Generate Test Cases" }).click();

  await expect(
    page.getByText(/Boundary scenario service unavailable/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Generate Test Cases" }),
  ).toBeEnabled();
  expect(requestBody).toMatchObject({
    repository_path: "/test/repository",
    test_types: ["boundary"],
    count: 3,
  });

  await page.getByRole("button", { name: "Generate Test Cases" }).click();
  await expect(
    page.getByRole("status").getByText(
      "No scenarios were returned for this request.",
    ),
  ).toBeVisible();
  expect(requestCount).toBe(2);
  expect(requestBody).toMatchObject({
    test_types: ["boundary"],
    count: 3,
  });
});

test("negative selection sends a negative-only request and renders scenarios", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  let releaseResponse!: () => void;
  const responseGate = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });

  await page.route("**/tests/generate", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await responseGate;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        generatedScenario("Reject request with missing prompt", "negative"),
      ),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByLabel("Scenario type").selectOption("negative");
  await page.getByLabel("Test case count").selectOption("10");
  await page.getByRole("button", { name: "Generate Test Cases" }).click();

  await expect.poll(() => requestBody).toMatchObject({
    repository_path: "/test/repository",
    test_types: ["negative"],
    count: 10,
  });
  expect(requestBody?.prompt).toContain("validation, rejection");
  expect(requestBody?.prompt).toContain("invalid or disallowed inputs");
  await expect(
    page.getByRole("button", { name: "Generating scenarios..." }),
  ).toBeDisabled();

  releaseResponse();
  await expect(
    page.getByText("Reject request with missing prompt"),
  ).toBeVisible();
  await expect(page.getByText("negative", { exact: true })).toBeVisible();
});

test("Negative Tests card starts a negative-only request", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  await page.route("**/tests/generate", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        generatedScenario("Negative card scenario", "negative"),
      ),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByRole("button", { name: /Negative Tests/ }).click();

  await expect(page.getByText("Negative card scenario")).toBeVisible();
  expect(requestBody).toMatchObject({
    repository_path: "/test/repository",
    test_types: ["negative"],
    count: 5,
  });
});

test("repository recommendation configures the executable test generation workflow", async ({
  page,
}) => {
  let codeGenerationRequest: Record<string, unknown> | undefined;
  let saveRequest: Record<string, unknown> | undefined;
  let saveAttempts = 0;
  const savedContent = 'import { test } from "@playwright/test";';
  await page.route("**/tests/generate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(generatedScenario("Scenario for codegen")),
    });
  });
  await page.route("**/repository/analyze", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        project_name: "test-repository",
        project_type: "node",
        languages: ["TypeScript"],
        frameworks: ["Playwright"],
        dependencies: [],
        test_files: [],
        automation_files: [
          {
            path: "playwright.config.ts",
            automation_type: "Playwright",
          },
        ],
        recommended_test_framework: "playwright",
        framework_recommendation_evidence: [
          "Existing automation file: playwright.config.ts",
        ],
        supported_test_frameworks: ["playwright", "selenium"],
        framework_support_evidence: {
          playwright: ["Existing automation file: playwright.config.ts"],
          selenium: ["Declared dependency: selenium-webdriver"],
        },
        supported_test_languages: ["TypeScript"],
      }),
    });
  });
  await page.route("**/tests/generate-code", async (route) => {
    codeGenerationRequest = route.request().postDataJSON() as Record<
      string,
      unknown
    >;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        generated_files: [
          {
            framework: "selenium",
            language: "typescript",
            file_path: "tests/testforge-generated.spec.ts",
            code: savedContent,
            test_case_ids: ["TC-INT-001"],
          },
        ],
        total_files: 1,
      }),
    });
  });
  await page.route("**/tests/save-code", async (route) => {
    saveAttempts += 1;
    saveRequest = route.request().postDataJSON() as Record<string, unknown>;
    if (saveAttempts === 1) {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "A file already exists at the generated destination.",
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "C:\\test\\repository",
        file_path: "C:\\test\\repository\\tests\\testforge-generated.spec.ts",
        relative_path: "tests/testforge-generated.spec.ts",
        code: savedContent,
      }),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByRole("button", { name: "Generate Test Cases" }).click();
  await expect(page.getByText("Scenario for codegen")).toBeVisible();
  await page.getByRole("button", { name: "Recommend Framework" }).click();
  await expect(page.getByText("Recommended: playwright")).toBeVisible();
  await expect(
    page.getByText("Evidence: Existing automation file: playwright.config.ts"),
  ).toBeVisible();
  await expect(page.getByLabel("Test framework")).toHaveValue("playwright");

  await page.getByLabel("Test framework").selectOption("selenium");
  await page.getByRole("button", { name: "Generate Executable Tests" }).click();
  await expect(page.getByText(/Validated code ready to save:/)).toBeVisible();
  expect(codeGenerationRequest).toMatchObject({
    repository_path: "/test/repository",
    framework: "selenium",
    language: "typescript",
    test_cases: [{ title: "Scenario for codegen" }],
  });
  expect(codeGenerationRequest?.output_file).toMatch(
    /^tests\/testforge-generated-\d+\.spec\.ts$/,
  );
  expect(saveAttempts).toBe(0);

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Save Generated Test" }).click();
  await expect(page.getByText(/Saved and opened in the editor:/)).toBeVisible();
  expect(saveAttempts).toBe(2);
  expect(saveRequest).toMatchObject({
    repository_path: "/test/repository",
    overwrite: true,
    generated_file: {
      framework: "selenium",
      code: savedContent,
    },
  });
  await expect.poll(async () =>
    page.evaluate(() => {
      const tab = window.testforgeActiveEditorTab();
      return tab
        ? { path: tab.path, content: tab.content, savedContent: tab.savedContent }
        : null;
    }),
  ).toEqual({
    path: "C:\\test\\repository\\tests\\testforge-generated.spec.ts",
    content: savedContent,
    savedContent,
  });
});

test("failed generated-code save does not open a file", async ({ page }) => {
  await page.route("**/tests/generate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(generatedScenario("Scenario for save failure")),
    });
  });
  await page.route("**/repository/analyze", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        project_name: "test-repository",
        project_type: "node",
        languages: ["TypeScript"],
        frameworks: ["Playwright"],
        dependencies: [],
        test_files: [],
        automation_files: [],
        recommended_test_framework: "playwright",
        framework_recommendation_evidence: ["Declared dependency: @playwright/test"],
        supported_test_frameworks: ["playwright"],
        framework_support_evidence: {
          playwright: ["Declared dependency: @playwright/test"],
        },
        supported_test_languages: ["TypeScript"],
      }),
    });
  });
  await page.route("**/tests/generate-code", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        generated_files: [{
          framework: "playwright",
          language: "typescript",
          file_path: "tests/generated.spec.ts",
          code: 'import { test } from "@playwright/test";',
          test_case_ids: ["TC-INT-001"],
        }],
        total_files: 1,
      }),
    });
  });
  await page.route("**/tests/save-code", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Generated test file could not be saved." }),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByRole("button", { name: "Generate Test Cases" }).click();
  await expect(page.getByText("Scenario for save failure")).toBeVisible();
  await page.getByRole("button", { name: "Recommend Framework" }).click();
  await page.getByRole("button", { name: "Generate Executable Tests" }).click();
  await page.getByRole("button", { name: "Save Generated Test" }).click();

  await expect(page.getByRole("alert").getByText(/could not be saved/)).toBeVisible();
  await expect.poll(async () =>
    page.evaluate(() => window.testforgeActiveEditorTab()),
  ).toBeNull();
});

test("incomplete generated-code response cannot be saved or opened", async ({
  page,
}) => {
  await page.route("**/tests/generate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(generatedScenario("Scenario for missing code")),
    });
  });
  await page.route("**/repository/analyze", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        project_name: "test-repository",
        project_type: "python",
        languages: ["Python"],
        frameworks: ["Pytest"],
        dependencies: [],
        test_files: [],
        automation_files: [],
        recommended_test_framework: "pytest",
        framework_recommendation_evidence: ["Detected configured framework: Pytest"],
        supported_test_frameworks: ["pytest"],
        framework_support_evidence: {
          pytest: ["Detected configured framework: Pytest"],
        },
        supported_test_languages: ["Python"],
      }),
    });
  });
  await page.route("**/tests/generate-code", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        generated_files: [],
        total_files: 0,
      }),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByRole("button", { name: "Generate Test Cases" }).click();
  await expect(page.getByText("Scenario for missing code")).toBeVisible();
  await page.getByRole("button", { name: "Recommend Framework" }).click();
  await page.getByRole("button", { name: "Generate Executable Tests" }).click();

  await expect(page.getByRole("alert").getByText(/response was incomplete/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Save Generated Test" })).toHaveCount(0);
  await expect.poll(async () =>
    page.evaluate(() => window.testforgeActiveEditorTab()),
  ).toBeNull();
});

test("missing saved-file metadata does not open generated code", async ({
  page,
}) => {
  await page.route("**/tests/generate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(generatedScenario("Scenario with missing save metadata")),
    });
  });
  await page.route("**/repository/analyze", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        project_name: "test-repository",
        project_type: "python",
        languages: ["Python"],
        frameworks: ["Pytest"],
        dependencies: [],
        test_files: [],
        automation_files: [],
        recommended_test_framework: "pytest",
        framework_recommendation_evidence: ["Detected configured framework: Pytest"],
        supported_test_frameworks: ["pytest"],
        framework_support_evidence: {
          pytest: ["Detected configured framework: Pytest"],
        },
        supported_test_languages: ["Python"],
      }),
    });
  });
  await page.route("**/tests/generate-code", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        generated_files: [{
          framework: "pytest",
          language: "python",
          file_path: "tests/generated_test.py",
          code: "def test_scenario():\n    assert True",
          test_case_ids: ["TC-INT-001"],
        }],
        total_files: 1,
      }),
    });
  });
  await page.route("**/tests/save-code", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        file_path: "/test/repository/tests/generated_test.py",
        code: "def test_scenario():\n    assert True",
      }),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByRole("button", { name: "Generate Test Cases" }).click();
  await expect(page.getByText("Scenario with missing save metadata")).toBeVisible();
  await page.getByRole("button", { name: "Recommend Framework" }).click();
  await page.getByRole("button", { name: "Generate Executable Tests" }).click();
  await page.getByRole("button", { name: "Save Generated Test" }).click();

  await expect(
    page.getByRole("alert").getByText(/did not include matching saved-file metadata/),
  ).toBeVisible();
  await expect(
    page.getByText(/Saved and opened in the editor:/),
  ).toHaveCount(0);
  await expect.poll(async () =>
    page.evaluate(() => window.testforgeActiveEditorTab()),
  ).toBeNull();
});

test("framework recommendation reports insufficient evidence", async ({
  page,
}) => {
  await page.route("**/repository/analyze", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        project_name: "test-repository",
        project_type: "unknown",
        languages: [],
        frameworks: [],
        dependencies: [],
        test_files: [],
        automation_files: [],
        recommended_test_framework: null,
        framework_recommendation_evidence: [],
      }),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByRole("button", { name: "Recommend Framework" }).click();
  await expect(
    page.getByRole("status").getByText(/No supported test framework/),
  ).toBeVisible();
  await expect(page.getByLabel("Test framework")).toHaveValue("");
});

test("negative generation errors recover to the explicit empty state", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  let requestCount = 0;
  await page.route("**/tests/generate", async (route) => {
    requestCount += 1;
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    if (requestCount === 1) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Negative scenario service unavailable",
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        test_cases: [],
        total_tests: 0,
      }),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByLabel("Scenario type").selectOption("negative");
  await page.getByLabel("Test case count").selectOption("3");
  await page.getByRole("button", { name: "Generate Test Cases" }).click();

  await expect(
    page.getByText(/Negative scenario service unavailable/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Generate Test Cases" }),
  ).toBeEnabled();
  expect(requestBody).toMatchObject({
    repository_path: "/test/repository",
    test_types: ["negative"],
    count: 3,
  });

  await page.getByRole("button", { name: "Generate Test Cases" }).click();
  await expect(
    page.getByRole("status").getByText(
      "No scenarios were returned for this request.",
    ),
  ).toBeVisible();
  expect(requestCount).toBe(2);
  expect(requestBody).toMatchObject({
    test_types: ["negative"],
    count: 3,
  });
});

test("functional scenario selection remains available and API failures/empty results are handled", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  let requestCount = 0;
  await page.route("**/tests/generate", async (route) => {
    requestCount += 1;
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    if (requestCount === 1) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "API scenario service unavailable" }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        test_cases: [],
        total_tests: 0,
      }),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByLabel("Scenario type").selectOption("functional");
  await page.getByLabel("Test case count").selectOption("3");
  await page.getByRole("button", { name: "Generate Test Cases" }).click();

  await expect(page.getByText(/API scenario service unavailable/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Generate Test Cases" }),
  ).toBeEnabled();
  expect(requestBody).toMatchObject({
    test_types: ["functional"],
    count: 3,
  });
  expect(requestBody?.prompt).toContain("comprehensive repository-aware test scenarios");

  await page.getByLabel("Scenario type").selectOption("api");
  await page.getByRole("button", { name: "Generate Test Cases" }).click();
  await expect(page.getByText("0 cases")).toBeVisible();
  await expect(
    page.getByRole("status").getByText(
      "No scenarios were returned for this request.",
    ),
  ).toBeVisible();
  expect(requestBody).toMatchObject({
    test_types: ["api"],
    count: 3,
  });
});

test("scenario generation errors are visible and allow retry", async ({
  page,
}) => {
  let requestCount = 0;
  await page.route("**/tests/generate", async (route) => {
    requestCount += 1;
    if (requestCount === 1) {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Scenario generation unavailable" }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(generatedScenario("Retry integration scenario")),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByLabel("Scenario type").selectOption("integration");
  await page.getByRole("button", { name: "Generate Test Cases" }).click();
  await expect(page.getByText(/Scenario generation unavailable/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Generate Test Cases" }),
  ).toBeEnabled();

  await page.getByRole("button", { name: "Generate Test Cases" }).click();
  await expect(page.getByText("Retry integration scenario")).toBeVisible();
  expect(requestCount).toBe(2);
});

test("empty scenario response is rendered as an explicit empty state", async ({
  page,
}) => {
  await page.route("**/tests/generate", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repository_path: "/test/repository",
        test_cases: [],
        total_tests: 0,
      }),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await page.getByLabel("Scenario type").selectOption("integration");
  await page.getByRole("button", { name: "Generate Test Cases" }).click();

  await expect(
    page.getByRole("status").getByText(
      "No scenarios were returned for this request.",
    ),
  ).toBeVisible();
  await expect(page.getByText("0 cases")).toBeVisible();
});

test("Run Test submits the selected repository, file, framework, and timeout once", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  let requestCount = 0;
  let releaseResponse!: () => void;
  const responseGate = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  await page.route("**/execution/run", async (route) => {
    requestCount += 1;
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await responseGate;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(executionResponse()),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open test fixture" }).click();
  await expect(page.getByLabel("Execution framework")).toHaveValue("pytest");
  await page.getByRole("button", { name: "Run Test" }).click();
  await expect(page.getByRole("status").getByText(/Running pytest test/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Run Test" })).toBeDisabled();
  await page.evaluate(() => {
    window.dispatchEvent(new CustomEvent("testforge:run-tests"));
    window.dispatchEvent(new CustomEvent("testforge:run-current-test"));
  });
  await expect.poll(() => requestCount).toBe(1);
  expect(requestBody).toMatchObject({
    repository_path: "/test/repository",
    file_path: "tests/test_orders.py",
    framework: "pytest",
    timeout_seconds: 120,
    measure_coverage: false,
  });

  releaseResponse();
  await expect(page.getByRole("status").getByText("Passed")).toBeVisible();
  await expect(page.getByText("Duration: 0.25s · Exit code: 0")).toBeVisible();
  expect(requestCount).toBe(1);
});

test("Run Test can explicitly request measured Python coverage", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  await page.route("**/execution/run", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        executionResponse({
          coverage_percent: 66.67,
          coverage_covered_statements: 2,
          coverage_total_statements: 3,
          source_digest: "a".repeat(64),
        }),
      ),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open test fixture" }).click();
  await page.getByLabel("Measure Python statement coverage (experimental)").check();
  await page.getByRole("button", { name: "Run Test" }).click();

  await expect(
    page.getByText("Python statement coverage: 66.67% (2 of 3)"),
  ).toBeVisible();
  expect(requestBody).toMatchObject({ measure_coverage: true });
});

test("Run Test rejects incompatible files without sending a request", async ({
  page,
}) => {
  let requestCount = 0;
  await page.route("**/execution/run", async (route) => {
    requestCount += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(executionResponse()),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open invalid test fixture" }).click();
  await expect(
    page.getByRole("alert").getByText(/active file must be a supported test file/),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Run Test" })).toBeDisabled();
  expect(requestCount).toBe(0);
});

test("Run Test selects Playwright for browser files and sends that framework", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  await page.route("**/execution/run", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(executionResponse({
        file_path: "web/tests/orders.spec.ts",
        framework: "playwright",
      })),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open browser test fixture" }).click();
  await expect(page.getByLabel("Execution framework")).toHaveValue("playwright");
  await page.getByRole("button", { name: "Run Test" }).click();
  await expect(page.getByRole("status").getByText("Passed")).toBeVisible();
  expect(requestBody).toMatchObject({
    repository_path: "/test/repository",
    file_path: "web/tests/orders.spec.ts",
    framework: "playwright",
  });
});

test("Run Test allows explicit Selenium selection for Python tests", async ({
  page,
}) => {
  let requestBody: Record<string, unknown> | undefined;
  await page.route("**/execution/run", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(executionResponse({
        framework: "selenium",
      })),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open test fixture" }).click();
  await page.getByLabel("Execution framework").selectOption("selenium");
  await expect(page.getByLabel("Execution framework")).toHaveValue("selenium");
  await page.getByRole("button", { name: "Run Test" }).click();
  await expect(page.getByRole("status").getByText("Passed")).toBeVisible();
  expect(requestBody).toMatchObject({
    repository_path: "/test/repository",
    file_path: "tests/test_orders.py",
    framework: "selenium",
  });
});

test("Run Test displays failed, runner-error, timeout, and skipped results distinctly", async ({
  page,
}) => {
  const results = [
    { status: "failed", exit_code: 1, title: "Failed" },
    {
      status: "error",
      exit_code: null,
      error: "Pytest runner is unavailable.",
      title: "Runner error",
    },
    {
      status: "timeout",
      exit_code: null,
      error: "Execution timed out.",
      title: "Timed out",
    },
    { status: "skipped", exit_code: 0, stdout: "1 skipped", title: "Skipped" },
  ];
  let requestIndex = 0;
  await page.route("**/execution/run", async (route) => {
    const result = results[requestIndex];
    requestIndex += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(executionResponse(result)),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open test fixture" }).click();
  for (const result of results) {
    await page.getByRole("button", { name: "Run Test" }).click();
    await expect(page.getByRole("status").getByText(result.title)).toBeVisible();
  }
});

test("Run Test reports request errors and rejects malformed or stale responses", async ({
  page,
}) => {
  let mode:
    | "request-error"
    | "malformed"
    | "inconsistent"
    | "stale" = "request-error";
  let releaseResponse!: () => void;
  const responseGate = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  await page.route("**/execution/run", async (route) => {
    if (mode === "request-error") {
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Selected test file is invalid." }),
      });
    } else if (mode === "malformed") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "passed" }),
      });
    } else if (mode === "inconsistent") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(executionResponse({
          status: "passed",
          exit_code: 1,
        })),
      });
    } else {
      await responseGate;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(executionResponse()),
      });
    }
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open test fixture" }).click();
  await page.getByRole("button", { name: "Run Test" }).click();
  await expect(
    page.getByRole("alert").getByText(/Execution request rejected/),
  ).toBeVisible();

  mode = "malformed";
  await page.getByRole("button", { name: "Run Test" }).click();
  await expect(page.getByRole("alert").getByText(/incomplete result/)).toBeVisible();
  await expect(page.getByRole("status").getByText("Passed")).toHaveCount(0);

  mode = "inconsistent";
  await page.getByRole("button", { name: "Run Test" }).click();
  await expect(page.getByRole("alert").getByText(/mismatched result/)).toBeVisible();
  await expect(page.getByRole("status").getByText("Passed")).toHaveCount(0);

  mode = "stale";
  await page.getByRole("button", { name: "Run Test" }).click();
  await expect(page.getByRole("status").getByText(/Running pytest test/)).toBeVisible();
  await page.getByRole("button", { name: "Open invalid test fixture" }).click();
  releaseResponse();
  await expect(page.getByRole("status").getByText("Passed")).toHaveCount(0);
});

test("Execution output keeps stdout, stderr, status, exit code, and duration distinct", async ({
  page,
}) => {
  await page.route("**/execution/run", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(executionResponse({
        status: "failed",
        exit_code: 1,
        stdout: "stdout marker",
        stderr: "stderr marker",
        duration_seconds: 1.75,
      })),
    });
  });
  await openPanel(page);
  await page.getByRole("button", { name: "Open test fixture" }).click();
  await page.getByRole("button", { name: "Run Test" }).click();
  await expect(page.getByLabel("Execution stdout")).toContainText("stdout marker");
  await expect(page.getByLabel("Execution stderr")).toContainText("stderr marker");
  await expect(page.getByText("Duration: 1.75s · Exit code: 1")).toBeVisible();
  await expect(page.getByRole("status").getByText("Failed")).toBeVisible();
});

test("Execution output displays explicit empty streams and missing exit code", async ({
  page,
}) => {
  await page.route("**/execution/run", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(executionResponse({
        status: "timeout",
        exit_code: null,
        stdout: "",
        stderr: "",
        error: "Process timed out after 1 seconds.",
      })),
    });
  });
  await openPanel(page);
  await page.getByRole("button", { name: "Open test fixture" }).click();
  await page.getByRole("button", { name: "Run Test" }).click();
  await expect(page.getByLabel("Execution stdout")).toContainText("No stdout output.");
  await expect(page.getByLabel("Execution stderr")).toContainText("No stderr output.");
  await expect(page.getByText("Duration: 0.25s · Exit code: not reported")).toBeVisible();
  await expect(page.getByText("Execution error: Process timed out after 1 seconds.")).toBeVisible();
});

test("RCA and repair candidate require review and explicit apply, then restore safely", async ({
  page,
}) => {
  const original = "def test_order():\n    assert True\n";
  const proposed = "def test_order():\n    assert 1 == 1\n";
  let applyCount = 0;
  let restoreCount = 0;
  let executionCount = 0;
  await page.route("**/execution/run", async (route) => {
    executionCount += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(executionResponse({
        status: "failed",
        exit_code: 1,
        stderr: "AssertionError: expected 4, got 3",
      })),
    });
  });
  await page.route("**/failure-analysis/analyze", async (route) => {
    expect(route.request().postDataJSON()).toMatchObject({
      execution: {
        status: "failed",
        file_path: "tests/test_orders.py",
        stderr: "AssertionError: expected 4, got 3",
      },
    });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        execution_id: "execution-1",
        execution_file: "tests/test_orders.py",
        execution_status: "failed",
        failure_type: "assertion_failure",
        observed_details: ["Execution output contains an assertion-failure indicator."],
        evidence: ["AssertionError: expected 4, got 3"],
        root_cause: null,
        inferred_explanation: null,
        recommendations: ["Compare expected and actual values."],
        severity: "medium",
        repair_required: true,
      }),
    });
  });
  await page.route("**/self-healing/repair", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repair_id: "repair-123",
        status: "generated",
        file_path: "tests/test_orders.py",
        target_line_start: 2,
        target_line_end: 2,
        original_code: original,
        repaired_code: proposed,
        explanation: "Proposed test correction.",
        changes: ["Changed assertion."],
        evidence: ["AssertionError: expected 4, got 3"],
        eligible_for_review: true,
      }),
    });
  });
  await page.route("**/self-healing/apply", async (route) => {
    applyCount += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repair_id: "repair-123",
        status: "applied",
        file_path: "tests/test_orders.py",
        code: proposed,
        message: "Repair applied after explicit approval.",
      }),
    });
  });
  await page.route("**/self-healing/restore", async (route) => {
    restoreCount += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        repair_id: "repair-123",
        status: "restored",
        file_path: "tests/test_orders.py",
        code: original,
        message: "The source was restored to its pre-repair contents.",
      }),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open test fixture" }).click();
  await page.getByRole("button", { name: "Run Test" }).click();
  await expect(page.getByText("No analysis has been requested for this execution.")).toBeVisible();
  await page.getByRole("button", { name: "Analyze failure", exact: true }).click();
  await expect(page.getByText("No confirmed root cause was identified from this execution.")).toBeVisible();
  await expect(page.getByLabel("Execution stderr")).toContainText(
    "AssertionError: expected 4, got 3",
  );
  await page.getByRole("button", { name: "Generate repair candidate" }).click();
  await expect(page.getByLabel("Repair code comparison")).toContainText(
    "- 2 |     assert True",
  );
  await expect(page.getByLabel("Repair code comparison")).toContainText(
    "+ 2 |     assert 1 == 1",
  );
  await expect(page.getByLabel("Original repair source")).toContainText(original);
  await expect(page.getByLabel("Proposed repair source")).toContainText(proposed);
  expect(applyCount).toBe(0);
  expect(restoreCount).toBe(0);
  await page.getByRole("button", { name: "Approve and apply repair" }).click();
  await expect(page.getByRole("status").getByText("Repair applied after explicit approval.")).toBeVisible();
  await expect.poll(async () =>
    page.evaluate(() => window.testforgeActiveEditorTab()?.content),
  ).toBe(proposed);
  expect(applyCount).toBe(1);
  expect(restoreCount).toBe(0);

  await page.getByRole("button", { name: "Restore original source" }).click();
  await expect(page.getByRole("status").getByText("The source was restored to its pre-repair contents.")).toBeVisible();
  await expect.poll(async () =>
    page.evaluate(() => window.testforgeActiveEditorTab()?.content),
  ).toBe(original);
  expect(restoreCount).toBe(1);
  expect(executionCount).toBe(1);
});

test("RCA reports analysis errors and ignores stale analysis after a new execution", async ({
  page,
}) => {
  let analysisMode: "error" | "malformed" | "pending" = "error";
  let releaseAnalysis!: () => void;
  const analysisGate = new Promise<void>((resolve) => {
    releaseAnalysis = resolve;
  });
  await page.route("**/execution/run", async (route) => {
    const request = route.request().postDataJSON() as { file_path: string };
    const isPythonTest = request.file_path.endsWith(".py");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(executionResponse({
        file_path: request.file_path,
        framework: isPythonTest ? "pytest" : "playwright",
        status: isPythonTest ? "failed" : "passed",
        exit_code: isPythonTest ? 1 : 0,
        stderr: isPythonTest ? "old failure evidence" : "",
      })),
    });
  });
  await page.route("**/failure-analysis/analyze", async (route) => {
    if (analysisMode === "error") {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Analysis service unavailable." }),
      });
    } else if (analysisMode === "malformed") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ failure_type: "unknown" }),
      });
    } else {
      await analysisGate;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          execution_id: "execution-1",
          execution_file: "tests/test_orders.py",
          execution_status: "failed",
          failure_type: "unknown",
          observed_details: ["old analysis"],
          evidence: ["old failure evidence"],
          root_cause: null,
          inferred_explanation: null,
          recommendations: [],
          severity: "medium",
          repair_required: false,
        }),
      });
    }
  });
  await openPanel(page);
  await page.getByRole("button", { name: "Open test fixture" }).click();
  await page.getByRole("button", { name: "Run Test" }).click();
  await page.getByRole("button", { name: "Analyze failure", exact: true }).click();
  await expect(page.getByRole("alert").getByText(/Analysis service unavailable/)).toBeVisible();

  analysisMode = "malformed";
  await page.getByRole("button", { name: "Analyze failure", exact: true }).click();
  await expect(page.getByRole("alert").getByText(/incomplete result/)).toBeVisible();

  analysisMode = "pending";
  await page.getByRole("button", { name: "Analyze failure", exact: true }).click();
  await expect(page.getByText("Analyzing execution evidence…")).toBeVisible();
  await page.getByRole("button", { name: "Open browser test fixture" }).click();
  await page.getByRole("button", { name: "Run Test" }).click();
  await expect(page.getByRole("status").getByText("Passed")).toBeVisible();
  releaseAnalysis();
  await expect(page.getByText("old analysis")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Generate repair candidate" })).toHaveCount(0);
});

test("RCA displays an explicitly returned root cause as a separate explanation", async ({
  page,
}) => {
  await page.route("**/execution/run", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(executionResponse({
        status: "failed",
        exit_code: 1,
        stderr: "ModuleNotFoundError: No module named 'example'",
      })),
    });
  });
  await page.route("**/failure-analysis/analyze", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        execution_id: "execution-1",
        execution_file: "tests/test_orders.py",
        execution_status: "failed",
        failure_type: "import_error",
        observed_details: ["Python import-resolution error was reported."],
        evidence: ["ModuleNotFoundError: No module named 'example'"],
        root_cause: "The test process could not import the declared module.",
        inferred_explanation: null,
        recommendations: ["Verify the selected project environment."],
        severity: "high",
        repair_required: false,
      }),
    });
  });
  await openPanel(page);
  await page.getByRole("button", { name: "Open test fixture" }).click();
  await page.getByRole("button", { name: "Run Test" }).click();
  await page.getByRole("button", { name: "Analyze failure", exact: true }).click();
  await expect(page.getByText("The test process could not import the declared module.")).toBeVisible();
  await expect(page.getByText("No confirmed root cause was identified from this execution.")).toHaveCount(0);
  await expect(page.getByText("Verify the selected project environment.")).toBeVisible();
});

test("analytics displays actual execution counts and the latest stored metrics", async ({
  page,
}) => {
  await page.route("**/history/executions**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: 2,
          execution_id: "exec-2",
          repository_path: "/test/repository",
          file_path: "tests/test_same.py",
          framework: "pytest",
          status: "failed",
          exit_code: 1,
          stdout: "",
          stderr: "",
          duration_seconds: 0.4,
          error: null,
          coverage_percent: 66.67,
          coverage_covered_statements: 2,
          coverage_total_statements: 3,
          coverage_error: null,
          source_digest: "b".repeat(64),
          created_at: "2025-01-02T00:00:00Z",
        },
        {
          id: 1,
          execution_id: "exec-1",
          repository_path: "/test/repository",
          file_path: "tests/test_same.py",
          framework: "pytest",
          status: "passed",
          exit_code: 0,
          stdout: "",
          stderr: "",
          duration_seconds: 0.2,
          error: null,
          coverage_percent: 50,
          coverage_covered_statements: 1,
          coverage_total_statements: 2,
          coverage_error: null,
          source_digest: "a".repeat(64),
          created_at: "2025-01-01T00:00:00Z",
        },
      ]),
    });
  });
  await page.route("**/history/analytics**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: 1,
          repository_path: "/test/repository",
          test_generation_validity: 100,
          coverage_before: 50,
          coverage_after: 66.67,
          coverage_improvement: 12.5,
          defect_detection_rate: 75,
          development_time_reduction: 20,
          maintenance_reduction: 10,
          self_healing_success_rate: 50,
          created_at: "2025-01-02T00:00:00Z",
        },
      ]),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open analytics" }).click();
  await expect(page.getByRole("group", { name: "Recent executions: 2" })).toBeVisible();
  await expect(page.getByRole("group", { name: "Passed: 1" })).toBeVisible();
  await expect(page.getByRole("group", { name: "Failed: 1" })).toBeVisible();
  await expect(page.getByText("Test Validity").locator("..")).toContainText("100.00%");
  await expect(
    page.getByText("Coverage before change").locator(".."),
  ).toContainText("50.00%");
  await expect(
    page.getByText("Coverage after change").locator(".."),
  ).toContainText("66.67%");
  await expect(page.getByText("Coverage improvement").locator("..")).toContainText(
    "16.67 pp",
  );
  await expect(page.getByText("Defect Detection").locator("..")).toContainText(
    "75.00%",
  );
});

test("analytics shows unavailable values when history has no measurements", async ({
  page,
}) => {
  await page.route("**/history/executions**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
  await page.route("**/history/analytics**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open analytics" }).click();
  await expect(page.getByRole("group", { name: "Recent executions: 0" })).toBeVisible();
  await expect(page.getByRole("group", { name: "Measured coverage: —" })).toBeVisible();
  await expect(page.getByText("Test Validity").locator("..")).toContainText("—");
});

test("analytics rejects malformed measured coverage without showing a percentage", async ({
  page,
}) => {
  await page.route("**/history/executions**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: 1,
          execution_id: "exec-malformed",
          repository_path: "/test/repository",
          file_path: "tests/test_sample.py",
          framework: "pytest",
          status: "passed",
          exit_code: 0,
          stdout: "",
          stderr: "",
          duration_seconds: 0.1,
          error: null,
          coverage_percent: 101,
          coverage_covered_statements: 2,
          coverage_total_statements: 3,
          coverage_error: null,
          source_digest: "a".repeat(64),
          created_at: "2025-01-02T00:00:00Z",
        },
      ]),
    });
  });
  await page.route("**/history/analytics**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await openPanel(page);
  await page.getByRole("button", { name: "Open analytics" }).click();

  await expect(
    page.getByRole("alert").getByText("Analytics history returned an incomplete response."),
  ).toBeVisible();
  await expect(page.getByRole("group", { name: "Measured coverage: —" })).toBeVisible();
});
