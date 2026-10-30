import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  FileSearch,
  GitBranch,
  Play,
  RotateCcw,
  Search,
  Sparkles,
  Wrench,
} from "lucide-react";

import type { ActivityView } from "../activity-bar/ActivityBar";
import {
  runTestExecution,
  analyzeFailure,
  applyRepair,
  restoreRepair,
  selfHeal,
  getAnalyticsHistory,
  getExecutionHistory,
  type AnalyticsHistoryItem,
  type ExecutionHistoryItem,
  type FailureAnalysisResult,
  type ExecutionStatus,
  type RepairOperationResponse,
  type SelfHealingResult,
  type TestExecutionResponse,
  type TestingFramework,
} from "../../services/testingApi";
import { ApiRequestError } from "../../services/api";
import { FailureHealingHistoryPanel } from "./FailureHealingHistoryPanel";
import { editorStore, useEditorStore } from "../stores/editorStore";
import {
  useRepositoryStore,
} from "../stores/repositoryStore";

interface ActivityPanelProps {
  view: ActivityView | string;
  onClose?: () => void;
}

export default function ActivityPanel({
  view,
}: ActivityPanelProps) {
  if (view === "search") {
    return <SearchPanel />;
  }

  if (view === "source-control") {
    return <SourceControlPanel />;
  }

  if (view === "run") {
    return <RunTestPanel />;
  }

  if (view === "analytics") {
    return <AnalyticsPanel />;
  }

  if (
    view === "history" ||
    view === "failure-history" ||
    view === "failure-healing" ||
    view === "failures" ||
    view === "healing"
  ) {
    return <FailureHealingHistoryPanel />;
  }

  if (view === "extensions") {
    return <ExtensionsPanel />;
  }

  return null;
}

/* -------------------------------------------------------------------------- */
/* SEARCH                                                                     */
/* -------------------------------------------------------------------------- */

function SearchPanel() {
  return (
    <aside className="flex h-full min-h-0 min-w-0 flex-col border-r border-[#252a33] bg-[#0d1117]">
      <PanelHeader title="SEARCH" />

      <div className="p-3">
        <div className="flex items-center gap-2 rounded border border-[#30363d] bg-[#161b22] px-2">
          <Search
            size={14}
            className="text-[#6e7681]"
          />

          <input
            type="text"
            placeholder="Search"
            className="h-8 min-w-0 flex-1 bg-transparent text-[12px] text-[#c9d1d9] outline-none placeholder:text-[#484f58]"
          />
        </div>

        <div className="mt-2 flex items-center gap-2">
          <button
            type="button"
            className="rounded border border-[#30363d] px-2 py-1 text-[10px] text-[#8b949e] hover:bg-[#21262d] hover:text-white"
          >
            Match Case
          </button>

          <button
            type="button"
            className="rounded border border-[#30363d] px-2 py-1 text-[10px] text-[#8b949e] hover:bg-[#21262d] hover:text-white"
          >
            Regex
          </button>
        </div>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <FileSearch
          size={34}
          strokeWidth={1.3}
          className="mb-3 text-[#484f58]"
        />

        <p className="text-xs text-[#8b949e]">
          Search your repository
        </p>

        <p className="mt-1 text-[10px] leading-4 text-[#484f58]">
          Search across source code,
          tests, documentation and
          configuration files.
        </p>
      </div>
    </aside>
  );
}

/* -------------------------------------------------------------------------- */
/* SOURCE CONTROL                                                             */
/* -------------------------------------------------------------------------- */

function SourceControlPanel() {
  return (
    <aside className="flex h-full min-h-0 min-w-0 flex-col border-r border-[#252a33] bg-[#0d1117]">
      <PanelHeader title="SOURCE CONTROL" />

      <div className="flex flex-1 flex-col">
        <div className="border-b border-[#1d222a] p-3">
          <button
            type="button"
            className="flex w-full items-center justify-center gap-2 rounded bg-blue-600 px-3 py-2 text-[11px] font-medium text-white hover:bg-blue-500"
          >
            <GitBranch size={14} />
            Initialize / Refresh
          </button>
        </div>

        <div className="px-3 py-4">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-[#6e7681]">
            Changes
          </p>

          <div className="rounded border border-[#21262d] bg-[#11161d] px-3 py-4 text-center">
            <GitBranch
              size={28}
              strokeWidth={1.3}
              className="mx-auto mb-2 text-[#484f58]"
            />

            <p className="text-[11px] text-[#8b949e]">
              No changes detected
            </p>

            <p className="mt-1 text-[9px] text-[#484f58]">
              Git integration will appear
              here when a repository is
              opened.
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}

/* -------------------------------------------------------------------------- */
/* RUN & TEST                                                                 */
/* -------------------------------------------------------------------------- */

function RunTestPanel() {
  const { tabs, activeTabId } = useEditorStore();
  const { rootPath } = useRepositoryStore();
  const activeTab = tabs.find((tab) => tab.id === activeTabId) ?? null;
  const activeTabPath = activeTab?.path ?? "";
  const [frameworkChoice, setFrameworkChoice] = useState<{
    path: string;
    framework: TestingFramework | "";
  }>({ path: "", framework: "" });
  const [measureCoverage, setMeasureCoverage] = useState(false);
  const [executionState, setExecutionState] = useState<{
    filePath: string;
    executionId: number;
    result: TestExecutionResponse;
  } | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [errorState, setErrorState] = useState<{
    filePath: string;
    message: string;
  } | null>(null);
  const isRunningRef = useRef(false);
  const requestIdRef = useRef(0);
  const executionSequenceRef = useRef(0);
  const analysisRequestRef = useRef(0);
  const repairRequestRef = useRef(0);
  const [analysisState, setAnalysisState] = useState<{
    executionId: number;
    result?: FailureAnalysisResult;
    loading: boolean;
    error?: string;
  } | null>(null);
  const [repairState, setRepairState] = useState<{
    executionId: number;
    candidate?: SelfHealingResult;
    loading: boolean;
    applying: boolean;
    applied: boolean;
    restored: boolean;
    error?: string;
    message?: string;
  } | null>(null);

  const relativeTestPath = (
    repositoryPath: string | null,
    filePath: string | undefined,
  ) => {
    if (!repositoryPath || !filePath) {
      return null;
    }
    const root = repositoryPath.replace(/[\\/]+$/, "");
    const selected = filePath.replace(/[\\/]+/g, "\\");
    const normalizedRoot = root.replace(/[\\/]+/g, "\\");
    const prefix = `${normalizedRoot}\\`;
    if (!selected.toLowerCase().startsWith(prefix.toLowerCase())) {
      return null;
    }
    const relative = selected.slice(prefix.length).replace(/\\/g, "/");
    if (!relative || relative.split("/").some((part) => part === "..")) {
      return null;
    }
    return relative;
  };

  const selectedFile = relativeTestPath(rootPath, activeTab?.path);
  const extension = selectedFile?.split(".").pop()?.toLowerCase();
  const compatible = useMemo(() => ({
    pytest:
      extension === "py" &&
      /(^|\/)test_.*\.py$|_test\.py$/i.test(selectedFile ?? ""),
    selenium:
      extension === "py" &&
      /(^|\/)test_.*\.py$|_test\.py$/i.test(selectedFile ?? ""),
    playwright:
      ["js", "cjs", "mjs", "ts"].includes(extension ?? "") &&
      /\.(?:spec|test)\.(?:js|cjs|mjs|ts)$/i.test(selectedFile ?? ""),
  }), [extension, selectedFile]);
  const inferredFramework: TestingFramework | "" =
    compatible.pytest ? "pytest" : compatible.playwright ? "playwright" : "";
  const framework =
    frameworkChoice.path === activeTabPath
      ? frameworkChoice.framework
      : inferredFramework;
  const execution =
    executionState?.filePath === selectedFile
      ? executionState.result
      : null;
  const executionId =
    executionState?.filePath === selectedFile
      ? executionState.executionId
      : null;
  const analysis =
    executionId !== null && analysisState?.executionId === executionId
      ? analysisState
      : null;
  const repair =
    executionId !== null && repairState?.executionId === executionId
      ? repairState
      : null;
  const error =
    errorState?.filePath === selectedFile
      ? errorState.message
      : null;

  const handleRun = useCallback(async () => {
    if (isRunningRef.current) {
      return;
    }
    if (!rootPath || !selectedFile || !framework || !compatible[framework]) {
      setErrorState({
        filePath: selectedFile ?? "",
        message:
          "Select a compatible test file and framework from the open repository.",
      });
      setExecutionState(null);
      return;
    }

    isRunningRef.current = true;
    const requestId = ++requestIdRef.current;
    const executionId = ++executionSequenceRef.current;
    const selectedPathAtStart = activeTabPath;
    setIsRunning(true);
    setErrorState(null);
    setExecutionState(null);
    try {
      const response: unknown = await runTestExecution({
        repository_path: rootPath,
        file_path: selectedFile,
        framework,
        timeout_seconds: 120,
        measure_coverage: measureCoverage && framework !== "playwright",
      });
      if (!isExecutionResponse(response)) {
        throw new Error("The execution service returned an incomplete result.");
      }
      if (
        normalizePath(response.repository_path) !== normalizePath(rootPath) ||
        response.framework !== framework ||
        normalizePath(response.file_path) !== normalizePath(selectedFile) ||
        response.status === "pending" ||
        response.status === "running" ||
        (response.status === "passed" &&
          (response.exit_code !== 0 || response.error !== null)) ||
        (response.status === "failed" &&
          (response.exit_code === null || response.exit_code === 0)) ||
        (response.status === "skipped" && response.exit_code !== 0) ||
        (response.status === "error" && response.exit_code === 0)
      ) {
        throw new Error("The execution service returned a mismatched result.");
      }
      if (requestId === requestIdRef.current) {
        const activeState = editorStore.getState();
        const selectedPath = activeState.tabs.find(
          (tab) => tab.id === activeState.activeTabId,
        )?.path;
        if (selectedPath !== selectedPathAtStart) {
          return;
        }
        setExecutionState({
          filePath: selectedFile,
          executionId,
          result: response,
        });
        setAnalysisState(null);
        setRepairState(null);
      }
    } catch (requestError) {
      if (requestId === requestIdRef.current) {
        const message =
          requestError instanceof Error
            ? requestError.message
            : "Test execution could not be completed.";
        setErrorState({
          filePath: selectedFile,
          message:
            requestError instanceof ApiRequestError &&
            requestError.status === 400
              ? `Execution request rejected: ${message}`
              : message,
        });
      }
    } finally {
      isRunningRef.current = false;
      setIsRunning(false);
    }
  }, [
    activeTabPath,
    compatible,
    framework,
    measureCoverage,
    rootPath,
    selectedFile,
    setAnalysisState,
    setErrorState,
    setRepairState,
    setExecutionState,
    setIsRunning,
  ]);

  const handleAnalyzeFailure = async () => {
    if (!execution || executionId === null) {
      return;
    }
    const requestId = ++analysisRequestRef.current;
    const selectedExecutionId = executionId;
    setAnalysisState({ executionId, loading: true });
    setRepairState(null);
    try {
      const response: unknown = await analyzeFailure({ execution });
      if (!isFailureAnalysisResult(response, execution)) {
        throw new Error("The failure analysis service returned an incomplete result.");
      }
      if (
        requestId === analysisRequestRef.current &&
        executionSequenceRef.current === selectedExecutionId
      ) {
        setAnalysisState({
          executionId: selectedExecutionId,
          result: response,
          loading: false,
        });
      }
    } catch (analysisError) {
      if (
        requestId === analysisRequestRef.current &&
        executionSequenceRef.current === selectedExecutionId
      ) {
        setAnalysisState({
          executionId: selectedExecutionId,
          loading: false,
          error:
            analysisError instanceof Error
              ? analysisError.message
              : "Failure analysis could not be completed.",
        });
      }
    }
  };

  const handleGenerateRepair = async () => {
    if (!execution || !analysis?.result || !rootPath || executionId === null) {
      return;
    }
    const openTab = editorStore.getState().tabs.find(
      (tab) => normalizePath(tab.path) === normalizePath(
        `${rootPath.replace(/[\\/]+$/, "")}/${execution.file_path}`,
      ),
    );
    if (openTab?.isDirty) {
      setRepairState({
        executionId,
        loading: false,
        applying: false,
        applied: false,
        restored: false,
        error: "Save or discard the current editor changes before generating a repair.",
      });
      return;
    }
    const requestId = ++repairRequestRef.current;
    const selectedExecutionId = executionId;
    setRepairState({
      executionId,
      loading: true,
      applying: false,
      applied: false,
      restored: false,
    });
    try {
      const response: unknown = await selfHeal({
        repository_path: rootPath,
        execution,
        analysis: analysis.result,
      });
      if (!isRepairCandidate(response, execution.file_path)) {
        throw new Error("The repair service returned an invalid candidate.");
      }
      if (
        requestId === repairRequestRef.current &&
        executionSequenceRef.current === selectedExecutionId
      ) {
        setRepairState({
          executionId: selectedExecutionId,
          candidate: response,
          loading: false,
          applying: false,
          applied: false,
          restored: false,
        });
      }
    } catch (repairError) {
      if (
        requestId === repairRequestRef.current &&
        executionSequenceRef.current === selectedExecutionId
      ) {
        setRepairState({
          executionId: selectedExecutionId,
          loading: false,
          applying: false,
          applied: false,
          restored: false,
          error:
            repairError instanceof Error
              ? repairError.message
              : "Repair candidate could not be generated.",
        });
      }
    }
  };

  const handleRepairOperation = async (
    operation: "apply" | "restore",
  ) => {
    if (!repair?.candidate || !repair.candidate.eligible_for_review || executionId === null) {
      return;
    }
    const selectedExecutionId = executionId;
    const candidate = repair.candidate;
    setRepairState({ ...repair, applying: true, error: undefined });
    try {
      const response: unknown =
        operation === "apply"
          ? await applyRepair({
              repair_id: candidate.repair_id,
              approved: true,
            })
          : await restoreRepair({
              repair_id: candidate.repair_id,
              approved: true,
            });
      if (!isRepairOperationResponse(response, candidate)) {
        throw new Error("The repair service returned an incomplete operation result.");
      }
      if (
        response.status !== (operation === "apply" ? "applied" : "restored")
      ) {
        throw new Error("The repair service returned a mismatched operation status.");
      }
      const editorUpdated = updateEditorAfterRepair(rootPath, response);
      if (executionSequenceRef.current === selectedExecutionId) {
        setRepairState({
          ...repair,
          applying: false,
          applied: operation === "apply" || repair.applied,
          restored: operation === "restore",
          message: editorUpdated
            ? response.message
            : `${response.message} The open editor has unsaved changes and was preserved.`,
        });
      }
    } catch (operationError) {
      setRepairState({
        ...repair,
        applying: false,
        error:
          operationError instanceof Error
            ? operationError.message
            : `Repair ${operation} failed.`,
      });
    }
  };

  useEffect(() => {
    const runCurrentFile = () => {
      void handleRun();
    };
    window.addEventListener("testforge:run-tests", runCurrentFile);
    window.addEventListener("testforge:run-current-test", runCurrentFile);
    return () => {
      window.removeEventListener("testforge:run-tests", runCurrentFile);
      window.removeEventListener("testforge:run-current-test", runCurrentFile);
      requestIdRef.current += 1;
    };
  }, [handleRun]);

  return (
    <aside className="flex h-full min-h-0 min-w-0 flex-col border-r border-[#252a33] bg-[#0d1117]">
      <PanelHeader title="RUN AND TEST" />

      <div className="flex flex-1 flex-col">
        <div className="border-b border-[#1d222a] p-3">
          <label className="mb-2 block text-[10px] text-[#8b949e]">
            Framework
            <select
              aria-label="Execution framework"
              className="mt-1 h-8 w-full rounded border border-[#30363d] bg-[#161b22] px-2 text-[11px] text-[#c9d1d9]"
              value={framework}
              onChange={(event) => {
                const value = event.target.value;
                if (
                  value === "" ||
                  value === "pytest" ||
                  value === "playwright" ||
                  value === "selenium"
                ) {
                  setFrameworkChoice({
                    path: activeTabPath,
                    framework: value,
                  });
                  if (value === "playwright") {
                    setMeasureCoverage(false);
                  }
                  setExecutionState(null);
                  setErrorState(null);
                }
              }}
              disabled={isRunning}
            >
              <option value="">Choose framework</option>
              <option value="pytest" disabled={!compatible.pytest}>Pytest</option>
              <option value="playwright" disabled={!compatible.playwright}>Playwright</option>
              <option value="selenium" disabled={!compatible.selenium}>Selenium</option>
            </select>
          </label>
          <p className="mb-2 break-all text-[9px] text-[#6e7681]">
            {activeTab?.path ?? "Open a test file in the editor to run it."}
          </p>
          <label className="mb-2 flex items-center gap-2 text-[9px] text-[#9da7b3]">
            <input
              type="checkbox"
              checked={measureCoverage}
              onChange={(event) => setMeasureCoverage(event.target.checked)}
              disabled={
                isRunning ||
                !framework ||
                framework === "playwright" ||
                !(compatible.pytest || compatible.selenium)
              }
            />
            Measure Python statement coverage (experimental)
          </label>
          <button
            type="button"
            aria-label="Run Test"
            onClick={() => void handleRun()}
            disabled={isRunning || !selectedFile || !framework || !compatible[framework]}
            className="flex w-full items-center justify-center gap-2 rounded bg-green-600 px-3 py-2 text-[11px] font-medium text-white hover:bg-green-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Play size={14} />
            {isRunning ? "Running Test..." : "Run Test"}
          </button>
          {activeTab && (!selectedFile || !Object.values(compatible).some(Boolean)) && (
            <p role="alert" className="mt-2 text-[9px] text-amber-300">
              The active file must be a supported test file inside the open repository.
            </p>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          {isRunning && (
            <p role="status" className="mb-3 text-[10px] text-blue-300">
              Running {framework} test: {selectedFile}
            </p>
          )}
          {error && (
            <p role="alert" className="mb-3 flex gap-2 text-[10px] text-red-300">
              <AlertCircle size={13} className="shrink-0" />
              {error}
            </p>
          )}
          {execution && (
            <>
              <ExecutionStatusView execution={execution} />
              {execution.status !== "passed" &&
                execution.status !== "skipped" && (
                  <section className="mt-3 space-y-2 rounded border border-[#30363d] bg-[#11161d] p-3">
                    <h3 className="text-[10px] font-semibold text-[#c9d1d9]">
                      Root Cause Analysis
                    </h3>
                    <button
                      type="button"
                      onClick={() => void handleAnalyzeFailure()}
                      disabled={analysis?.loading}
                      className="flex items-center gap-2 rounded border border-[#30363d] px-2 py-1 text-[10px] text-[#c9d1d9] hover:bg-[#21262d] disabled:opacity-50"
                    >
                      <Search size={12} />
                      {analysis?.loading ? "Analyzing..." : "Analyze failure"}
                    </button>
                    {!analysis && (
                      <p className="text-[9px] text-[#8b949e]">
                        No analysis has been requested for this execution.
                      </p>
                    )}
                    {analysis?.loading && (
                      <p role="status" className="text-[9px] text-blue-300">
                        Analyzing execution evidence…
                      </p>
                    )}
                    {analysis?.error && (
                      <p role="alert" className="text-[9px] text-red-300">
                        {analysis.error}
                      </p>
                    )}
                    {analysis && !analysis.loading && !analysis.error && !analysis.result && (
                      <p className="text-[9px] text-[#8b949e]">
                        No failure analysis is available for this execution yet.
                      </p>
                    )}
                    {analysis?.result && (
                      <FailureAnalysisView analysis={analysis.result} />
                    )}
                    {analysis?.result?.repair_required && (
                      <button
                        type="button"
                        onClick={() => void handleGenerateRepair()}
                        disabled={repair?.loading || repair?.applying}
                        className="flex items-center gap-2 rounded border border-amber-700 px-2 py-1 text-[10px] text-amber-200 hover:bg-[#21262d] disabled:opacity-50"
                      >
                        <Wrench size={12} />
                        {repair?.loading
                          ? "Generating candidate..."
                          : "Generate repair candidate"}
                      </button>
                    )}
                    {repair?.loading && (
                      <p role="status" className="text-[9px] text-blue-300">
                        Generating a review-only candidate…
                      </p>
                    )}
                    {repair?.error && (
                      <p role="alert" className="text-[9px] text-red-300">
                        {repair.error}
                      </p>
                    )}
                    {repair?.candidate && (
                      <RepairCandidateView
                        candidate={repair.candidate}
                        applied={repair.applied}
                        restored={repair.restored}
                        applying={repair.applying}
                        onApply={() => void handleRepairOperation("apply")}
                        onRestore={() => void handleRepairOperation("restore")}
                      />
                    )}
                    {repair?.message && (
                      <p role="status" className="text-[9px] text-green-300">
                        {repair.message}
                      </p>
                    )}
                  </section>
                )}
            </>
          )}
          {!isRunning && !error && !execution && (
            <p className="text-[10px] text-[#6e7681]">
              Select an open test file and explicitly run it to see its result.
            </p>
          )}
        </div>

        <div className="mt-auto border-t border-[#1d222a] p-3">
          <button
            type="button"
            onClick={() => {
              window.dispatchEvent(
                new CustomEvent(
                  "testforge:generate-tests",
                ),
              );
            }}
            className="flex w-full items-center justify-center gap-2 rounded border border-[#30363d] px-3 py-2 text-[10px] text-[#c9d1d9] hover:bg-[#21262d]"
          >
            <Sparkles size={13} />
            Generate Tests with AI
          </button>
        </div>
      </div>
    </aside>
  );
}

function ExecutionStatusView({
  execution,
}: {
  execution: TestExecutionResponse;
}) {
  const labels: Record<ExecutionStatus, string> = {
    pending: "Queued",
    running: "Running",
    passed: "Passed",
    failed: "Failed",
    skipped: "Skipped",
    timeout: "Timed out",
    error: "Runner error",
  };
  const success = execution.status === "passed";
  const Icon = success ? CheckCircle2 : AlertCircle;
  return (
    <div className="space-y-2 rounded border border-[#30363d] bg-[#11161d] p-3">
      <p
        role="status"
        className={`flex items-center gap-2 text-[11px] font-semibold ${
          success ? "text-green-300" : "text-amber-300"
        }`}
      >
        <Icon size={14} />
        {labels[execution.status]}
      </p>
      <p className="break-all text-[9px] text-[#9da7b3]">
        {execution.framework} · {execution.file_path}
      </p>
      <p className="text-[9px] text-[#8b949e]">
        Duration: {execution.duration_seconds.toFixed(2)}s
        {execution.exit_code !== null
          ? ` · Exit code: ${execution.exit_code}`
          : " · Exit code: not reported"}
      </p>
      {execution.coverage_percent !== null &&
        execution.coverage_percent !== undefined && (
          <p className="text-[9px] text-blue-200">
            Python statement coverage: {execution.coverage_percent.toFixed(2)}% (
            {execution.coverage_covered_statements} of {execution.coverage_total_statements})
          </p>
        )}
      {execution.coverage_error && (
        <p className="text-[9px] text-[#8b949e]">
          Coverage unavailable: {execution.coverage_error}
        </p>
      )}
      {execution.error && (
        <p className="break-words text-[9px] text-red-300">
          Execution error: {execution.error}
        </p>
      )}
      <div>
        <p className="mb-1 text-[9px] font-semibold text-[#9da7b3]">stdout</p>
        <pre
          aria-label="Execution stdout"
          className="max-h-40 overflow-auto whitespace-pre-wrap break-words text-[9px] text-[#c9d1d9]"
        >
          {execution.stdout || "No stdout output."}
        </pre>
      </div>
      <div>
        <p className="mb-1 text-[9px] font-semibold text-amber-200">stderr</p>
        <pre
          aria-label="Execution stderr"
          className="max-h-40 overflow-auto whitespace-pre-wrap break-words text-[9px] text-amber-200"
        >
          {execution.stderr || "No stderr output."}
        </pre>
      </div>
    </div>
  );
}

function FailureAnalysisView({
  analysis,
}: {
  analysis: FailureAnalysisResult;
}) {
  return (
    <div className="space-y-2 border-t border-[#30363d] pt-2">
      <p className="text-[9px] text-[#9da7b3]">
        {analysis.failure_type.replaceAll("_", " ")} · {analysis.severity} severity
      </p>
      <div>
        <p className="text-[9px] font-semibold text-[#c9d1d9]">Observed details</p>
        {analysis.observed_details.length > 0 ? (
          <ul className="list-disc space-y-1 pl-4 text-[9px] text-[#c9d1d9]">
            {analysis.observed_details.map((detail, index) => (
              <li key={`${index}-${detail}`}>{detail}</li>
            ))}
          </ul>
        ) : (
          <p className="text-[9px] text-[#8b949e]">No observed details returned.</p>
        )}
      </div>
      <div>
        <p className="text-[9px] font-semibold text-[#c9d1d9]">Execution evidence</p>
        {analysis.evidence.length > 0 ? (
          <pre className="max-h-32 overflow-auto whitespace-pre-wrap break-words text-[9px] text-[#9da7b3]">
            {analysis.evidence.join("\n")}
          </pre>
        ) : (
          <p className="text-[9px] text-[#8b949e]">No output evidence was available.</p>
        )}
      </div>
      <div>
        <p className="text-[9px] font-semibold text-[#c9d1d9]">Root cause</p>
        {analysis.root_cause ? (
          <p className="text-[9px] text-amber-200">{analysis.root_cause}</p>
        ) : (
          <p className="text-[9px] text-[#8b949e]">
            No confirmed root cause was identified from this execution.
          </p>
        )}
      </div>
      {analysis.inferred_explanation && (
        <p className="text-[9px] text-violet-200">
          Inferred explanation: {analysis.inferred_explanation}
        </p>
      )}
      {analysis.recommendations.length > 0 && (
        <div>
          <p className="text-[9px] font-semibold text-[#c9d1d9]">Recommended next steps</p>
          <ul className="list-disc space-y-1 pl-4 text-[9px] text-[#9da7b3]">
            {analysis.recommendations.map((recommendation, index) => (
              <li key={`${index}-${recommendation}`}>{recommendation}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function RepairCandidateView({
  candidate,
  applied,
  restored,
  applying,
  onApply,
  onRestore,
}: {
  candidate: SelfHealingResult;
  applied: boolean;
  restored: boolean;
  applying: boolean;
  onApply: () => void;
  onRestore: () => void;
}) {
  return (
    <div className="space-y-2 border-t border-[#30363d] pt-2">
      <p className="text-[10px] font-semibold text-[#c9d1d9]">
        Repair candidate · {candidate.file_path}
        {candidate.target_line_start
          ? ` · line ${candidate.target_line_start}${candidate.target_line_end && candidate.target_line_end !== candidate.target_line_start ? `-${candidate.target_line_end}` : ""}`
          : ""}
      </p>
      <p className="text-[9px] text-[#9da7b3]">{candidate.explanation}</p>
      <p className="text-[9px] font-semibold text-[#c9d1d9]">Original vs proposed changes</p>
      <pre
        aria-label="Repair code comparison"
        className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded border border-[#30363d] bg-[#090c10] p-2 text-[9px] text-[#c9d1d9]"
      >
        {formatRepairDiff(candidate.original_code, candidate.repaired_code)}
      </pre>
      <p className="text-[9px] font-semibold text-[#c9d1d9]">Original source</p>
      <pre aria-label="Original repair source" className="max-h-36 overflow-auto whitespace-pre-wrap break-words text-[9px] text-[#9da7b3]">
        {candidate.original_code}
      </pre>
      <p className="text-[9px] font-semibold text-[#c9d1d9]">Proposed source (not applied)</p>
      <pre aria-label="Proposed repair source" className="max-h-36 overflow-auto whitespace-pre-wrap break-words text-[9px] text-green-200">
        {candidate.repaired_code}
      </pre>
      {candidate.changes.length > 0 && (
        <ul className="list-disc pl-4 text-[9px] text-[#9da7b3]">
          {candidate.changes.map((change, index) => <li key={`${index}-${change}`}>{change}</li>)}
        </ul>
      )}
      {!applied && !restored && (
        <button
          type="button"
          onClick={onApply}
          disabled={applying}
          className="flex items-center gap-2 rounded bg-amber-700 px-2 py-1 text-[10px] text-white hover:bg-amber-600 disabled:opacity-50"
        >
          <Wrench size={12} />
          {applying ? "Applying..." : "Approve and apply repair"}
        </button>
      )}
      {applied && !restored && (
        <button
          type="button"
          onClick={onRestore}
          disabled={applying}
          className="flex items-center gap-2 rounded border border-[#30363d] px-2 py-1 text-[10px] text-[#c9d1d9] hover:bg-[#21262d] disabled:opacity-50"
        >
          <RotateCcw size={12} />
          {applying ? "Restoring..." : "Restore original source"}
        </button>
      )}
      {restored && (
        <p role="status" className="text-[9px] text-green-300">
          Original source restored. No tests were rerun.
        </p>
      )}
    </div>
  );
}

function formatRepairDiff(original: string, proposed: string): string {
  const originalLines = original.split(/\r?\n/);
  const proposedLines = proposed.split(/\r?\n/);
  let prefix = 0;
  while (
    prefix < originalLines.length &&
    prefix < proposedLines.length &&
    originalLines[prefix] === proposedLines[prefix]
  ) {
    prefix += 1;
  }

  let suffix = 0;
  while (
    suffix < originalLines.length - prefix &&
    suffix < proposedLines.length - prefix &&
    originalLines[originalLines.length - suffix - 1] ===
      proposedLines[proposedLines.length - suffix - 1]
  ) {
    suffix += 1;
  }

  const removed = originalLines
    .slice(prefix, originalLines.length - suffix)
    .map((line, index) => `- ${prefix + index + 1} | ${line}`);
  const added = proposedLines
    .slice(prefix, proposedLines.length - suffix)
    .map((line, index) => `+ ${prefix + index + 1} | ${line}`);
  const output = [
    ...(prefix > 0 ? [`... ${prefix} unchanged line(s) before`] : []),
    ...removed,
    ...added,
    ...(suffix > 0 ? [`... ${suffix} unchanged line(s) after`] : []),
  ];

  return output.length > 0 ? output.join("\n") : "No source changes.";
}

function normalizePath(path: string): string {
  return path.replace(/\\/g, "/").replace(/^\/+|\/+$/g, "").toLowerCase();
}

function isExecutionResponse(value: unknown): value is TestExecutionResponse {
  if (!value || typeof value !== "object") {
    return false;
  }
  const response = value as Partial<TestExecutionResponse>;
  const statuses: ExecutionStatus[] = [
    "pending",
    "running",
    "passed",
    "failed",
    "skipped",
    "timeout",
    "error",
  ];
  const coverageIsValid =
    response.coverage_percent === null
      ? response.coverage_covered_statements === null &&
        response.coverage_total_statements === null
      : typeof response.coverage_percent === "number" &&
        Number.isFinite(response.coverage_percent) &&
        response.coverage_percent >= 0 &&
        response.coverage_percent <= 100 &&
        typeof response.coverage_covered_statements === "number" &&
        Number.isInteger(response.coverage_covered_statements) &&
        response.coverage_covered_statements >= 0 &&
        typeof response.coverage_total_statements === "number" &&
        Number.isInteger(response.coverage_total_statements) &&
        response.coverage_total_statements > 0 &&
        response.coverage_covered_statements <= response.coverage_total_statements &&
        Math.abs(
          response.coverage_percent -
            (response.coverage_covered_statements /
              response.coverage_total_statements) *
              100,
        ) <= 0.01;
  return (
    typeof response.repository_path === "string" &&
    typeof response.execution_id === "string" &&
    typeof response.file_path === "string" &&
    (response.framework === "pytest" ||
      response.framework === "playwright" ||
      response.framework === "selenium") &&
    statuses.includes(response.status as ExecutionStatus) &&
    (response.exit_code === null || typeof response.exit_code === "number") &&
    typeof response.stdout === "string" &&
    typeof response.stderr === "string" &&
    typeof response.duration_seconds === "number" &&
    Number.isFinite(response.duration_seconds) &&
    response.duration_seconds >= 0 &&
    (response.error === null || typeof response.error === "string") &&
    coverageIsValid &&
    (response.coverage_error === null ||
      typeof response.coverage_error === "string") &&
    (response.source_digest === null ||
      (typeof response.source_digest === "string" &&
        /^[0-9a-f]{64}$/.test(response.source_digest)))
  );
}

function isFailureAnalysisResult(
  value: unknown,
  execution: TestExecutionResponse,
): value is FailureAnalysisResult {
  if (!value || typeof value !== "object") {
    return false;
  }
  const result = value as Partial<FailureAnalysisResult>;
  return (
    result.execution_id === execution.execution_id &&
    result.execution_file === execution.file_path &&
    result.execution_status === execution.status &&
    typeof result.failure_type === "string" &&
    Array.isArray(result.observed_details) &&
    result.observed_details.every((item) => typeof item === "string") &&
    Array.isArray(result.evidence) &&
    result.evidence.every((item) => typeof item === "string") &&
    (result.root_cause === null || typeof result.root_cause === "string") &&
    (result.inferred_explanation === null ||
      typeof result.inferred_explanation === "string") &&
    Array.isArray(result.recommendations) &&
    result.recommendations.every((item) => typeof item === "string") &&
    typeof result.severity === "string" &&
    typeof result.repair_required === "boolean"
  );
}

function isRepairCandidate(
  value: unknown,
  expectedPath: string,
): value is SelfHealingResult {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<SelfHealingResult>;
  return (
    typeof candidate.repair_id === "string" &&
    candidate.status === "generated" &&
    candidate.file_path === expectedPath &&
    (candidate.target_line_start === null ||
      typeof candidate.target_line_start === "number") &&
    (candidate.target_line_end === null ||
      typeof candidate.target_line_end === "number") &&
    typeof candidate.original_code === "string" &&
    typeof candidate.repaired_code === "string" &&
    candidate.original_code !== candidate.repaired_code &&
    typeof candidate.explanation === "string" &&
    Array.isArray(candidate.changes) &&
    candidate.changes.every((item) => typeof item === "string") &&
    Array.isArray(candidate.evidence) &&
    candidate.evidence.every((item) => typeof item === "string") &&
    candidate.eligible_for_review === true
  );
}

function isRepairOperationResponse(
  value: unknown,
  candidate: SelfHealingResult,
): value is RepairOperationResponse {
  if (!value || typeof value !== "object") {
    return false;
  }
  const result = value as Partial<RepairOperationResponse>;
  return (
    result.repair_id === candidate.repair_id &&
    (result.status === "applied" || result.status === "restored") &&
    result.file_path === candidate.file_path &&
    typeof result.code === "string" &&
    typeof result.message === "string"
  );
}

function updateEditorAfterRepair(
  repositoryPath: string | null,
  response: RepairOperationResponse,
): boolean {
  if (!repositoryPath) {
    return false;
  }
  const fullPath = `${repositoryPath.replace(/[\\/]+$/, "")}/${response.file_path}`;
  const tab = editorStore.getState().tabs.find(
    (item) => normalizePath(item.path) === normalizePath(fullPath),
  );
  if (tab?.isDirty) {
    return false;
  }
  if (tab) {
    editorStore.markSaved(tab.id, response.code);
    return true;
  }
  window.dispatchEvent(
    new CustomEvent("testforge:open-file", {
      detail: {
        path: fullPath,
        name: fullPath.split(/[\\/]/).pop(),
        content: response.code,
      },
    }),
  );
  return true;
}

/* -------------------------------------------------------------------------- */
/* ANALYTICS                                                                  */
/* -------------------------------------------------------------------------- */

function AnalyticsPanel() {
  const { rootPath } = useRepositoryStore();
  const [executions, setExecutions] = useState<ExecutionHistoryItem[] | null>(null);
  const [latestMetrics, setLatestMetrics] = useState<AnalyticsHistoryItem | null>(null);
  const [loadedRepositoryPath, setLoadedRepositoryPath] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!rootPath) {
      return () => {
        active = false;
      };
    }

    void Promise.all([
      getExecutionHistory(rootPath, 200),
      getAnalyticsHistory(rootPath, 1),
    ])
      .then(([executionHistory, analyticsHistory]) => {
        if (!isExecutionHistory(executionHistory) || !isAnalyticsHistory(analyticsHistory)) {
          throw new Error("Analytics history returned an incomplete response.");
        }
        if (active) {
          setExecutions(executionHistory);
          setLatestMetrics(analyticsHistory[0] ?? null);
          setLoadedRepositoryPath(rootPath);
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          setLoadedRepositoryPath(rootPath);
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Analytics history could not be loaded.",
          );
          setExecutions(null);
          setLatestMetrics(null);
        }
      });

    return () => {
      active = false;
    };
  }, [rootPath]);

  const isCurrentRepositoryLoaded = loadedRepositoryPath === rootPath;
  const displayedExecutions = isCurrentRepositoryLoaded ? executions : null;
  const metrics = isCurrentRepositoryLoaded ? latestMetrics : null;
  const displayedError = isCurrentRepositoryLoaded ? error : null;
  const isLoading = Boolean(rootPath) && !isCurrentRepositoryLoaded;
  const testCount = displayedExecutions?.length ?? 0;
  const passedCount = displayedExecutions?.filter((item) => item.status === "passed").length ?? 0;
  const failedCount = displayedExecutions?.filter((item) => item.status === "failed").length ?? 0;
  const coverageComparison = getCoverageComparison(displayedExecutions ?? []);

  return (
    <aside className="flex h-full min-h-0 min-w-0 flex-col border-r border-[#252a33] bg-[#0d1117]">
      <PanelHeader title="TEST ANALYTICS" />

      <div className="flex flex-1 flex-col overflow-y-auto p-3">
        {isLoading && <p role="status" className="mb-3 text-[10px] text-[#8b949e]">Loading analytics...</p>}
        {displayedError && <p role="alert" className="mb-3 text-[10px] text-red-300">{displayedError}</p>}
        {!rootPath && (
          <p className="mb-3 text-[10px] text-[#8b949e]">Open a repository to view its analytics.</p>
        )}
        <div className="mb-4 rounded border border-[#21262d] bg-[#11161d] p-3">
          <div className="mb-2 flex items-center gap-2">
            <BarChart3
              size={16}
              className="text-blue-400"
            />

            <span className="text-xs font-semibold text-[#c9d1d9]">
              Test Overview
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <Metric label="Recent executions" value={displayedExecutions ? String(testCount) : "—"} />
            <Metric label="Passed" value={displayedExecutions ? String(passedCount) : "—"} />
            <Metric label="Failed" value={displayedExecutions ? String(failedCount) : "—"} />
            <Metric
              label="Measured coverage"
              value={formatAnalyticsPercent(coverageComparison.after?.coverage_percent ?? undefined)}
            />
          </div>
        </div>

        <MetricRow
          label="Test Validity"
          value={formatAnalyticsPercent(metrics?.test_generation_validity)}
        />

        <MetricRow
          label="Coverage before change"
          value={formatAnalyticsPercent(coverageComparison.before?.coverage_percent ?? undefined)}
        />
        <MetricRow
          label="Coverage after change"
          value={formatAnalyticsPercent(coverageComparison.after?.coverage_percent ?? undefined)}
        />
        <MetricRow
          label="Coverage improvement"
          value={formatAnalyticsValue(coverageComparison.improvement, " pp")}
        />

        <MetricRow
          label="Defect Detection"
          value={formatAnalyticsPercent(metrics?.defect_detection_rate)}
        />

        <MetricRow
          label="Development Time"
          value={formatAnalyticsPercent(metrics?.development_time_reduction)}
        />

        <MetricRow
          label="Maintenance Reduction"
          value={formatAnalyticsPercent(metrics?.maintenance_reduction)}
        />

        <MetricRow
          label="Self-Healing Success"
          value={formatAnalyticsPercent(metrics?.self_healing_success_rate)}
        />
      </div>
    </aside>
  );
}

export { FailureHealingHistoryPanel } from "./FailureHealingHistoryPanel";

function isExecutionHistory(value: unknown): value is ExecutionHistoryItem[] {
  return Array.isArray(value) && value.every((item: unknown) => {
    if (!item || typeof item !== "object") {
      return false;
    }
    const record = item as Record<string, unknown>;
    const coverage = record.coverage_percent;
    const covered = record.coverage_covered_statements;
    const total = record.coverage_total_statements;
    return (
      typeof record.id === "number" &&
      Number.isInteger(record.id) &&
      typeof record.execution_id === "string" &&
      typeof record.repository_path === "string" &&
      typeof record.file_path === "string" &&
      (record.framework === "pytest" ||
        record.framework === "playwright" ||
        record.framework === "selenium") &&
      typeof record.status === "string" &&
      (record.exit_code === null ||
        (typeof record.exit_code === "number" &&
          Number.isInteger(record.exit_code))) &&
      typeof record.stdout === "string" &&
      typeof record.stderr === "string" &&
      typeof record.duration_seconds === "number" &&
      Number.isFinite(record.duration_seconds) &&
      (record.error === null || typeof record.error === "string") &&
      typeof record.created_at === "string" &&
      Number.isFinite(Date.parse(record.created_at)) &&
      (coverage === null
        ? covered === null && total === null
        : (typeof coverage === "number" &&
          Number.isFinite(coverage) &&
          coverage >= 0 &&
          coverage <= 100 &&
          typeof covered === "number" &&
          typeof total === "number" &&
          total > 0 &&
          covered <= total &&
          Math.abs(coverage - (covered / total) * 100) <= 0.01)) &&
      (covered === null ||
        (typeof covered === "number" &&
          Number.isInteger(covered) &&
          covered >= 0)) &&
      (total === null ||
        (typeof total === "number" && Number.isInteger(total) && total >= 0)) &&
      (record.coverage_error === null ||
        typeof record.coverage_error === "string") &&
      (record.source_digest === null ||
        (typeof record.source_digest === "string" &&
          /^[0-9a-f]{64}$/.test(record.source_digest)))
    );
  });
}

function isAnalyticsHistory(value: unknown): value is AnalyticsHistoryItem[] {
  const metrics: (keyof AnalyticsHistoryItem)[] = [
    "test_generation_validity",
    "coverage_improvement",
    "defect_detection_rate",
    "development_time_reduction",
    "maintenance_reduction",
    "self_healing_success_rate",
  ];
  return Array.isArray(value) && value.every((item: unknown) => {
    if (!item || typeof item !== "object") {
      return false;
    }
    const record = item as Record<string, unknown>;
    return (
      typeof record.id === "number" &&
      Number.isInteger(record.id) &&
      typeof record.repository_path === "string" &&
      typeof record.created_at === "string" &&
      Number.isFinite(Date.parse(record.created_at)) &&
      metrics.every((key) => {
        const metric = record[key];
        if (key === "coverage_improvement") {
          return (
            metric === null ||
            (typeof metric === "number" &&
              Number.isFinite(metric) &&
              metric >= -100 &&
              metric <= 100)
          );
        }
        if (
          key === "development_time_reduction" ||
          key === "maintenance_reduction"
        ) {
          return (
            typeof metric === "number" &&
            Number.isFinite(metric) &&
            metric <= 100
          );
        }
        return (
          typeof metric === "number" &&
          Number.isFinite(metric) &&
          metric >= 0 &&
          metric <= 100
        );
      }) &&
      [record.coverage_before, record.coverage_after].every(
        (coverage) =>
          coverage === null ||
          (typeof coverage === "number" &&
            Number.isFinite(coverage) &&
            coverage >= 0 &&
            coverage <= 100),
      )
    );
  });
}

function getCoverageComparison(executions: ExecutionHistoryItem[]) {
  const measured = executions.filter(
    (item) =>
      Number.isFinite(item.coverage_percent) &&
      item.coverage_percent !== null &&
      typeof item.source_digest === "string",
  );
  const after = measured[0];
  if (!after || after.coverage_percent === null || !after.source_digest) {
    return { before: undefined, after: undefined, improvement: undefined };
  }
  const before = measured[1];
  if (
    !before ||
    before.file_path !== after.file_path ||
    before.framework !== after.framework ||
    before.source_digest === after.source_digest ||
    before.coverage_percent === null
  ) {
    return { before: undefined, after, improvement: undefined };
  }
  return {
    before,
    after,
    improvement: after.coverage_percent - before.coverage_percent,
  };
}

function formatAnalyticsPercent(value: number | undefined): string {
  return value === undefined ? "—" : `${value.toFixed(2)}%`;
}

function formatAnalyticsValue(value: number | undefined, suffix: string): string {
  return value === undefined ? "—" : `${value.toFixed(2)}${suffix}`;
}

/* -------------------------------------------------------------------------- */
/* SHARED COMPONENTS                                                          */
/* -------------------------------------------------------------------------- */

function PanelHeader({
  title,
}: {
  title: string;
}) {
  return (
    <div className="flex h-10 shrink-0 items-center border-b border-[#1d222a] px-3">
      <span className="text-[11px] font-semibold tracking-wide text-[#8b949e]">
        {title}
      </span>
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div
      role="group"
      aria-label={`${label}: ${value}`}
      className="rounded border border-[#21262d] bg-[#0d1117] p-2"
    >
      <p className="text-[9px] text-[#6e7681]">
        {label}
      </p>

      <p className="mt-1 text-sm font-semibold text-[#c9d1d9]">
        {value}
      </p>
    </div>
  );
}

function MetricRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between border-b border-[#1d222a] py-2">
      <span className="text-[10px] text-[#8b949e]">
        {label}
      </span>

      <span className="text-[10px] font-medium text-[#c9d1d9]">
        {value}
      </span>
    </div>
  );
}

function ExtensionsPanel() {
  return (
    <aside className="flex h-full min-h-0 min-w-0 flex-col border-r border-[#252a33] bg-[#0d1117]">
      <PanelHeader title="EXTENSIONS" />
      <div className="border-b border-[#1d222a] p-3">
        <input aria-label="Search extensions" placeholder="Search extensions" className="h-8 w-full rounded border border-[#30363d] bg-[#161b22] px-2 text-[11px] text-[#c9d1d9] outline-none placeholder:text-[#6e7681] focus:border-[#3794ff]" />
      </div>
      <div className="p-3 text-[10px] font-semibold uppercase tracking-wide text-[#6e7681]">Built in</div>
      <div className="space-y-1 px-2">
        {[["Monaco Editor", "Code editing and language services"], ["TestForge Testing", "Repository analysis and test generation"], ["Integrated Terminal", "Run workspace commands"]].map(([name, description]) => (
          <div key={name} className="flex gap-3 rounded px-2 py-2 hover:bg-[#161b22]">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded border border-[#30363d] bg-[#1e1e1e] text-[10px] font-bold text-[#3794ff]">TF</div>
            <div className="min-w-0"><div className="text-[11px] text-[#d7dae0]">{name}</div><div className="mt-1 text-[9px] leading-4 text-[#858585]">{description}</div><div className="mt-1 text-[9px] text-[#6a9955]">Enabled</div></div>
          </div>
        ))}
      </div>
    </aside>
  );
}
