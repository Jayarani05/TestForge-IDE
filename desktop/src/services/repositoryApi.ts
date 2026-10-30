import { apiGet, apiPost } from "./api";

export interface RepositoryInspectResponse {
  [key: string]: unknown;
}

export interface RepositoryTreeResponse {
  repository_path: string;
  files: {
    name: string;
    path: string;
    relative_path: string;
    extension: string | null;
    language: string | null;
    size_bytes: number;
  }[];
  directories: {
    name: string;
    path: string;
    relative_path: string;
  }[];
}

export interface RepositoryAnalyzeResponse {
  [key: string]: unknown;
  repository_path: string;
  project_name: string;
  project_type: string;
  languages: string[];
  frameworks: string[];
  dependencies: {
    name: string;
    version?: string | null;
    source_file: string;
  }[];
  test_files: {
    path: string;
    framework?: string | null;
    language?: string | null;
  }[];
  automation_files: {
    path: string;
    automation_type: string;
  }[];
  recommended_test_framework?: "pytest" | "playwright" | "selenium" | null;
  framework_recommendation_evidence?: string[];
  supported_test_frameworks?: ("pytest" | "playwright" | "selenium")[];
  framework_support_evidence?: Record<string, string[]>;
  supported_test_languages?: string[];
}

export async function inspectRepository(
  repositoryPath: string,
): Promise<RepositoryInspectResponse> {
  return apiPost<RepositoryInspectResponse>(
    "/repository/inspect",
    {
      path: repositoryPath,
    },
  );
}

export async function getRepositoryTree(
  repositoryPath: string,
): Promise<RepositoryTreeResponse> {
  return apiGet<RepositoryTreeResponse>(
    `/repository/tree?path=${encodeURIComponent(
      repositoryPath,
    )}`,
  );
}

export async function analyzeRepository(
  repositoryPath: string,
): Promise<RepositoryAnalyzeResponse> {
  return apiPost<RepositoryAnalyzeResponse>(
    "/repository/analyze",
    {
      path: repositoryPath,
    },
  );
}

export async function indexRepositoryContext(
  repositoryPath: string,
): Promise<Record<string, unknown>> {
  return apiPost<Record<string, unknown>>(
    "/context/index",
    {
      path: repositoryPath,
    },
  );
}
