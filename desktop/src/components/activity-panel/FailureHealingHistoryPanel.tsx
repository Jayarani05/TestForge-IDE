import { useEffect, useState } from "react";

import {
  getFailureHistory,
  getSelfHealingHistory,
  type FailureHistoryItem,
  type SelfHealingHistoryItem,
} from "../../services/testingApi";
import { useRepositoryStore } from "../stores/repositoryStore";

function PanelHeader({ title }: { title: string }) {
  return (
    <div className="flex h-9 items-center border-b border-[#252a33] px-3">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-[#8b949e]">
        {title}
      </span>
    </div>
  );
}

export function FailureHealingHistoryPanel() {
  const { rootPath } = useRepositoryStore();
  const [failures, setFailures] = useState<FailureHistoryItem[] | null>(null);
  const [healings, setHealings] = useState<SelfHealingHistoryItem[] | null>(null);
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
      getFailureHistory(rootPath, 200),
      getSelfHealingHistory(rootPath, 200),
    ])
      .then(([failureHistory, healingHistory]) => {
        if (
          !isFailureHistory(failureHistory) ||
          !isSelfHealingHistory(healingHistory)
        ) {
          throw new Error(
            "Failure and healing history returned an incomplete response.",
          );
        }
        if (active) {
          setFailures(failureHistory);
          setHealings(healingHistory);
          setLoadedRepositoryPath(rootPath);
          setError(null);
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          setLoadedRepositoryPath(rootPath);
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Failure and healing history could not be loaded.",
          );
          setFailures(null);
          setHealings(null);
        }
      });

    return () => {
      active = false;
    };
  }, [rootPath]);

  const isCurrentRepositoryLoaded = loadedRepositoryPath === rootPath;
  const displayedFailures = isCurrentRepositoryLoaded ? failures : null;
  const displayedHealings = isCurrentRepositoryLoaded ? healings : null;
  const displayedError = isCurrentRepositoryLoaded ? error : null;
  const isLoading = Boolean(rootPath) && !isCurrentRepositoryLoaded;

  return (
    <aside className="flex h-full min-h-0 min-w-0 flex-col border-r border-[#252a33] bg-[#0d1117]">
      <PanelHeader title="FAILURE AND HEALING HISTORY" />

      <div className="flex flex-1 flex-col overflow-y-auto p-3">
        {isLoading && (
          <p role="status" className="mb-3 text-[10px] text-[#8b949e]">
            Loading failure and healing history...
          </p>
        )}
        {displayedError && (
          <p role="alert" className="mb-3 text-[10px] text-red-300">
            {displayedError}
          </p>
        )}
        {!rootPath && (
          <p className="mb-3 text-[10px] text-[#8b949e]">
            Open a repository to view failure and healing history.
          </p>
        )}

        {isCurrentRepositoryLoaded &&
          (displayedFailures?.length ?? 0) === 0 &&
          (displayedHealings?.length ?? 0) === 0 &&
          !displayedError && (
            <p className="mb-3 text-[10px] text-[#8b949e]">
              No failure or healing history is available.
            </p>
          )}
        {(displayedFailures ?? []).map((item) => (
          <div
            key={`failure-${item.id}`}
            className="mb-3 rounded border border-[#21262d] bg-[#11161d] p-3"
          >
            <div className="mb-2 text-[11px] font-semibold text-[#c9d1d9]">
              Failure record #{item.id}
            </div>
            <div className="space-y-1 text-[10px] text-[#8b949e]">
              <div>Execution ID: {item.execution_id ?? "—"}</div>
              <div>Failure ID: {item.id}</div>
              <div>Failure type: {item.failure_type ?? "—"}</div>
              <div>Failure status: {item.failure_type ?? "—"}</div>
              <div>Severity: {item.severity ?? "—"}</div>
              <div>Root cause: {item.root_cause ?? "—"}</div>
              <div>Suggested fix: {item.suggested_fix ?? "—"}</div>
              <div>Repair required: {String(item.repair_required ?? false)}</div>
              <div>Timestamp: {item.created_at ?? "—"}</div>
            </div>

            <div className="mt-2">
              <div className="text-[10px] font-semibold text-[#c9d1d9]">
                Observed evidence
              </div>
              <ul className="mt-1 list-disc pl-4 text-[10px] text-[#8b949e]">
                {(item.evidence ?? item.observed_details ?? []).map(
                  (entry, index) => (
                    <li key={`evidence-${item.id}-${index}`}>{entry}</li>
                  ),
                )}
                {(item.evidence ?? item.observed_details ?? []).length === 0 && (
                  <li>None recorded.</li>
                )}
              </ul>
            </div>

            <div className="mt-2">
              <div className="text-[10px] font-semibold text-[#c9d1d9]">
                Inferred explanation (not observed evidence)
              </div>
              <p className="mt-1 text-[10px] text-[#8b949e]">
                {item.inferred_explanation ?? "—"}
              </p>
            </div>

            {(item.recommendations ?? []).length > 0 && (
              <div className="mt-2">
                <div className="text-[10px] font-semibold text-[#c9d1d9]">
                  Recommendations
                </div>
                <ul className="mt-1 list-disc pl-4 text-[10px] text-[#8b949e]">
                  {(item.recommendations ?? []).map((entry, index) => (
                    <li key={`recommendation-${item.id}-${index}`}>{entry}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}

        {(displayedHealings ?? []).map((item) => (
          <div
            key={`healing-${item.id}`}
            className="mb-3 rounded border border-[#21262d] bg-[#11161d] p-3"
          >
            <div className="mb-2 text-[11px] font-semibold text-[#c9d1d9]">
              Healing record #{item.id}
            </div>
            <div className="space-y-1 text-[10px] text-[#8b949e]">
              <div>Healing record ID: {item.id}</div>
              <div>Repair ID: {item.repair_id ?? "—"}</div>
              <div>Execution ID: {item.execution_id ?? "—"}</div>
              <div>Failure analysis ID: {item.failure_analysis_id ?? "—"}</div>
              <div>Failure type: {item.failure_type ?? "—"}</div>
              <div>Repair lifecycle status: {item.status ?? "—"}</div>
              <div>Review status: {item.review_status ?? "—"}</div>
              <div>Apply outcome: {item.apply_outcome ?? "—"}</div>
              <div>Restore outcome: {item.restore_outcome ?? "—"}</div>
              <div>Applied at: {item.applied_at ?? "—"}</div>
              <div>Restored at: {item.restored_at ?? "—"}</div>
              <div>Timestamp: {item.created_at ?? "—"}</div>
            </div>

            <div className="mt-2">
              <div className="text-[10px] font-semibold text-[#c9d1d9]">
                Repair candidate
              </div>
              <p className="mt-1 text-[10px] text-[#8b949e]">
                {item.explanation ?? "—"}
              </p>
              <p className="mt-1 text-[10px] text-[#8b949e]">
                {item.changes ?? "—"}
              </p>
            </div>
            {(item.original_code !== null || item.proposed_code !== null) && (
              <div className="mt-2">
                <div className="text-[10px] font-semibold text-[#c9d1d9]">
                  Original versus proposed source
                </div>
                <div className="mt-1 grid grid-cols-2 gap-2">
                  <pre
                    aria-label="Original repair source"
                    className="max-h-36 overflow-auto whitespace-pre-wrap break-words rounded border border-[#30363d] bg-[#0d1117] p-2 text-[9px] text-[#c9d1d9]"
                  >
                    {item.original_code ?? "—"}
                  </pre>
                  <pre
                    aria-label="Proposed repair source"
                    className="max-h-36 overflow-auto whitespace-pre-wrap break-words rounded border border-[#30363d] bg-[#0d1117] p-2 text-[9px] text-[#c9d1d9]"
                  >
                    {item.proposed_code ?? "—"}
                  </pre>
                </div>
              </div>
            )}
          </div>
        ))}

      </div>
    </aside>
  );
}

function isFailureHistory(value: unknown): value is FailureHistoryItem[] {
  return (
    Array.isArray(value) &&
    value.every((item: unknown) => {
      if (!item || typeof item !== "object") {
        return false;
      }
      const record = item as Record<string, unknown>;
      return (
        typeof record.id === "number" &&
        Number.isInteger(record.id) &&
        typeof record.repository_path === "string" &&
        typeof record.file_path === "string" &&
        typeof record.failure_type === "string" &&
        typeof record.severity === "string" &&
        typeof record.suggested_fix === "string" &&
        typeof record.repair_required === "boolean" &&
        typeof record.created_at === "string" &&
        Number.isFinite(Date.parse(record.created_at))
      );
    })
  );
}

function isSelfHealingHistory(value: unknown): value is SelfHealingHistoryItem[] {
  return (
    Array.isArray(value) &&
    value.every((item: unknown) => {
      if (!item || typeof item !== "object") {
        return false;
      }
      const record = item as Record<string, unknown>;
      return (
        typeof record.id === "number" &&
        Number.isInteger(record.id) &&
        typeof record.repository_path === "string" &&
        typeof record.file_path === "string" &&
        typeof record.failure_type === "string" &&
        typeof record.status === "string" &&
        typeof record.explanation === "string" &&
        typeof record.changes === "string" &&
        typeof record.created_at === "string" &&
        Number.isFinite(Date.parse(record.created_at))
      );
    })
  );
}

export default FailureHealingHistoryPanel;