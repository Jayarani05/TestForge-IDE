import { apiGet } from "./api";

export async function getExecutionHistory(
  repositoryPath?: string,
) {
  const query = repositoryPath
    ? `?repository_path=${encodeURIComponent(repositoryPath)}`
    : "";

  return apiGet<unknown[]>(
    `/history/executions${query}`,
  );
}

export async function getFailureHistory(
  repositoryPath?: string,
) {
  const query = repositoryPath
    ? `?repository_path=${encodeURIComponent(repositoryPath)}`
    : "";

  return apiGet<unknown[]>(
    `/history/failures${query}`,
  );
}

export async function getSelfHealingHistory(
  repositoryPath?: string,
) {
  const query = repositoryPath
    ? `?repository_path=${encodeURIComponent(repositoryPath)}`
    : "";

  return apiGet<unknown[]>(
    `/history/self-healing${query}`,
  );
}

export async function getAnalyticsHistory(
  repositoryPath?: string,
) {
  const query = repositoryPath
    ? `?repository_path=${encodeURIComponent(repositoryPath)}`
    : "";

  return apiGet<unknown[]>(
    `/history/analytics${query}`,
  );
}
