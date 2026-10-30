import { useSyncExternalStore } from "react";

interface RepositoryState {
  rootPath: string | null;
  rootName: string | null;
  analysis: Record<string, unknown> | null;
  isAnalyzing: boolean;
  error: string | null;
}

let state: RepositoryState = {
  rootPath: null,
  rootName: null,
  analysis: null,
  isAnalyzing: false,
  error: null,
};

const listeners =
  new Set<() => void>();

function emit() {
  listeners.forEach(
    (listener) => listener(),
  );
}

export const repositoryStore = {
  getState() {
    return state;
  },

  subscribe(
    listener: () => void,
  ) {
    listeners.add(listener);

    return () =>
      listeners.delete(
        listener,
      );
  },

  setRepository(
    rootPath: string,
  ) {
    state = {
      ...state,
      rootPath,
      rootName:
        rootPath
          .split(/[\\/]/)
          .pop() ??
        "Repository",
      error: null,
    };

    emit();
  },

  setAnalysis(
    analysis: Record<
      string,
      unknown
    >,
  ) {
    state = {
      ...state,
      analysis,
      isAnalyzing: false,
      error: null,
    };

    emit();
  },

  setAnalyzing(
    value: boolean,
  ) {
    state = {
      ...state,
      isAnalyzing: value,
      error: null,
    };

    emit();
  },

  setError(
    error: string,
  ) {
    state = {
      ...state,
      isAnalyzing: false,
      error,
    };

    emit();
  },

  clearRepository() {
    state = {
      rootPath: null,
      rootName: null,
      analysis: null,
      isAnalyzing: false,
      error: null,
    };

    emit();
  },
};

export function useRepositoryStore() {
  return useSyncExternalStore(
    repositoryStore.subscribe,
    repositoryStore.getState,
  );
}