import { apiGet, apiPost } from "./api";

/* ========================================================================== */
/* TYPES                                                                      */
/* ========================================================================== */

export type TestingFramework =
  | "pytest"
  | "playwright"
  | "selenium";

export interface IntelligentTestingRequest {
  repository_path: string;
  file_path: string;
  framework?: TestingFramework;
  timeout_seconds?: number;
  args?: string[];
  source_code?: string;
}

export type ExecutionStatus =
  | "pending"
  | "running"
  | "passed"
  | "failed"
  | "skipped"
  | "timeout"
  | "error";

export interface TestExecutionRequest {
  repository_path: string;
  file_path: string;
  framework: TestingFramework;
  timeout_seconds?: number;
  args?: string[];
  measure_coverage?: boolean;
}

export interface TestExecutionResponse {
  execution_id: string;
  repository_path: string;
  file_path: string;
  framework: TestingFramework;
  status: ExecutionStatus;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  duration_seconds: number;
  error: string | null;
  coverage_percent: number | null;
  coverage_covered_statements: number | null;
  coverage_total_statements: number | null;
  coverage_error: string | null;
  source_digest: string | null;
}

export interface IntelligentTestingResponse {
  execution: Record<string, unknown>;
  failure_analysis: Record<string, unknown> | null;
  self_healing: Record<string, unknown> | null;
  re_execution: Record<string, unknown> | null;
  analytics: Record<string, unknown> | null;
}

export interface TestGenerationRequest {
  repository_path: string;
  prompt?: string;
  test_types?: TestType[];
  count?: number;
}

export type TestType =
  | "functional"
  | "integration"
  | "api"
  | "regression"
  | "boundary"
  | "negative"
  | "exception"
  | "edge_case";

export interface GeneratedTestCase {
  id: string;
  title: string;
  description: string;
  test_type: TestType;
  priority: string;
  preconditions: string[];
  steps: string[];
  expected_result: string;
  target_file?: string | null;
  target_function?: string | null;
}

export interface TestGenerationResponse {
  repository_path: string;
  test_cases: GeneratedTestCase[];
  total_tests: number;
}

export interface TestCodeGenerationRequest {
  repository_path: string;
  test_cases: GeneratedTestCase[];
  framework: TestingFramework;
  language: "python" | "javascript" | "typescript";
  output_file: string;
}

export interface GeneratedTestCode {
  framework: TestingFramework;
  language: "python" | "javascript" | "typescript";
  file_path: string;
  code: string;
  test_case_ids: string[];
}

export interface TestCodeGenerationResponse {
  repository_path: string;
  generated_files: GeneratedTestCode[];
  total_files: number;
  context_available?: boolean;
  context_warning?: string | null;
}

export interface SaveGeneratedTestCodeRequest {
  repository_path: string;
  generated_file: GeneratedTestCode;
  overwrite?: boolean;
}

export interface SaveGeneratedTestCodeResponse {
  repository_path: string;
  file_path: string;
  relative_path: string;
  code: string;
}

export interface FailureAnalysisRequest {
  execution: TestExecutionResponse;
}

export interface FailureAnalysisResult {
  execution_id: string;
  failure_type: string;
  execution_file: string;
  execution_status: ExecutionStatus;
  observed_details: string[];
  evidence: string[];
  root_cause: string | null;
  inferred_explanation: string | null;
  recommendations: string[];
  severity: string;
  repair_required: boolean;
}

export interface SelfHealingRequest {
  repository_path: string;
  execution: TestExecutionResponse;
  analysis: FailureAnalysisResult;
  provider?: string;
}

export interface SelfHealingResult {
  repair_id: string;
  status: "generated";
  file_path: string;
  target_line_start: number | null;
  target_line_end: number | null;
  original_code: string;
  repaired_code: string;
  explanation: string;
  changes: string[];
  evidence: string[];
  eligible_for_review: boolean;
}

export interface RepairOperationRequest {
  repair_id: string;
  approved: boolean;
}

export interface RepairOperationResponse {
  repair_id: string;
  status: "applied" | "restored";
  file_path: string;
  code: string;
  message: string;
}

export interface ExecutionHistoryItem {
  id: number;
  execution_id: string;
  repository_path: string;
  file_path: string;
  framework: TestingFramework;
  status: string;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  duration_seconds: number;
  error: string | null;
  coverage_percent: number | null;
  coverage_covered_statements: number | null;
  coverage_total_statements: number | null;
  coverage_error: string | null;
  source_digest: string | null;
  created_at: string;
}

export interface FailureHistoryItem {
  id: number;
  repository_path: string;
  file_path: string;
  failure_type: string;
  root_cause: string | null;
  severity: string;
  suggested_fix: string;
  repair_required: boolean;
  execution_id: string | null;
  observed_details: string[];
  evidence: string[];
  inferred_explanation: string | null;
  recommendations: string[];
  created_at: string;
}

export interface SelfHealingHistoryItem {
  id: number;
  repair_id: string | null;
  execution_id: string | null;
  failure_analysis_id: number | null;
  repository_path: string;
  file_path: string;
  failure_type: string;
  status: string;
  explanation: string;
  changes: string;
  original_code: string | null;
  proposed_code: string | null;
  review_status: string | null;
  apply_approved: boolean | null;
  apply_outcome: string | null;
  restore_outcome: string | null;
  applied_at: string | null;
  restored_at: string | null;
  created_at: string;
}

export interface AnalyticsHistoryItem {
  id: number;
  repository_path: string;
  test_generation_validity: number;
  coverage_before: number | null;
  coverage_after: number | null;
  coverage_improvement: number | null;
  defect_detection_rate: number;
  development_time_reduction: number;
  maintenance_reduction: number;
  self_healing_success_rate: number;
  created_at: string;
}

/* ========================================================================== */
/* INTELLIGENT TESTING                                                        */
/* ========================================================================== */

export async function runIntelligentTesting(
  request: IntelligentTestingRequest,
): Promise<IntelligentTestingResponse> {
  return apiPost<IntelligentTestingResponse>(
    "/intelligent-testing/run",
    request,
  );
}

/* ========================================================================== */
/* TEST GENERATION                                                            */
/* ========================================================================== */

export async function generateTests(
  repositoryPath: string,
  prompt = "",
  testTypes: TestType[] = [
    "functional",
    "integration",
    "api",
    "regression",
    "boundary",
    "negative",
    "exception",
    "edge_case",
  ],
  count = 5,
): Promise<TestGenerationResponse> {
  const request: TestGenerationRequest = {
    repository_path: repositoryPath,
    prompt,
    test_types: testTypes,
    count,
  };

  return apiPost<TestGenerationResponse>(
    "/tests/generate",
    request,
  );
}

/* ========================================================================== */
/* TEST CODE GENERATION                                                       */
/* ========================================================================== */

export async function generateTestCode(
  request: TestCodeGenerationRequest,
): Promise<TestCodeGenerationResponse> {
  return apiPost<TestCodeGenerationResponse>(
    "/tests/generate-code",
    request,
  );
}

export async function saveGeneratedTestCode(
  request: SaveGeneratedTestCodeRequest,
): Promise<SaveGeneratedTestCodeResponse> {
  return apiPost<SaveGeneratedTestCodeResponse>(
    "/tests/save-code",
    request,
  );
}

/* ========================================================================== */
/* TEST EXECUTION                                                             */
/* ========================================================================== */

export async function runTestExecution(
  request: TestExecutionRequest,
): Promise<TestExecutionResponse> {
  return apiPost<TestExecutionResponse>(
    "/execution/run",
    request,
  );
}

/* ========================================================================== */
/* FAILURE ANALYSIS                                                           */
/* ========================================================================== */

export async function analyzeFailure(
  request: FailureAnalysisRequest,
): Promise<FailureAnalysisResult> {
  return apiPost<FailureAnalysisResult>(
    "/failure-analysis/analyze",
    request,
  );
}

/* ========================================================================== */
/* SELF HEALING                                                               */
/* ========================================================================== */

export async function selfHeal(
  request: SelfHealingRequest,
): Promise<SelfHealingResult> {
  return apiPost<SelfHealingResult>(
    "/self-healing/repair",
    request,
  );
}

export async function applyRepair(
  request: RepairOperationRequest,
): Promise<RepairOperationResponse> {
  return apiPost<RepairOperationResponse>(
    "/self-healing/apply",
    request,
  );
}

export async function restoreRepair(
  request: RepairOperationRequest,
): Promise<RepairOperationResponse> {
  return apiPost<RepairOperationResponse>(
    "/self-healing/restore",
    request,
  );
}

/* ========================================================================== */
/* EXECUTION HISTORY                                                          */
/* ========================================================================== */

export async function getExecutionHistory(
  repositoryPath: string,
  limit = 20,
): Promise<ExecutionHistoryItem[]> {
  return apiGet<ExecutionHistoryItem[]>(
    `/history/executions?repository_path=${encodeURIComponent(
      repositoryPath,
    )}&limit=${limit}`,
  );
}

/* ========================================================================== */
/* FAILURE HISTORY                                                            */
/* ========================================================================== */

export async function getFailureHistory(
  repositoryPath: string,
  limit = 20,
): Promise<FailureHistoryItem[]> {
  return apiGet<FailureHistoryItem[]>(
    `/history/failures?repository_path=${encodeURIComponent(
      repositoryPath,
    )}&limit=${limit}`,
  );
}

/* ========================================================================== */
/* SELF-HEALING HISTORY                                                       */
/* ========================================================================== */

export async function getSelfHealingHistory(
  repositoryPath: string,
  limit = 20,
): Promise<SelfHealingHistoryItem[]> {
  return apiGet<SelfHealingHistoryItem[]>(
    `/history/self-healing?repository_path=${encodeURIComponent(
      repositoryPath,
    )}&limit=${limit}`,
  );
}

/* ========================================================================== */
/* ANALYTICS HISTORY                                                          */
/* ========================================================================== */

export async function getAnalyticsHistory(
  repositoryPath: string,
  limit = 20,
): Promise<AnalyticsHistoryItem[]> {
  return apiGet<AnalyticsHistoryItem[]>(
    `/history/analytics?repository_path=${encodeURIComponent(
      repositoryPath,
    )}&limit=${limit}`,
  );
}