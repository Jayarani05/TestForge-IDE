import { useEffect, useState } from "react";

import {
  AlertCircle,
  ChevronDown,
  FolderOpen,
  FolderPlus,
  FilePlus2,
  Loader2,
  RefreshCw,
} from "lucide-react";

import {
  openRepository,
  readDirectory,
} from "../../services/fileSystem";

import type { FileSystemEntry } from "../../types/electron";

import FileTree from "./FileTree";
import { repositoryStore } from "../stores/repositoryStore";

interface ExplorerProps {
  onFileOpen?: (path: string) => void;
  onRepositoryOpened?: (path: string) => void;
}

export default function Explorer({
  onFileOpen,
  onRepositoryOpened,
}: ExplorerProps) {
  /* =========================================================
     STATE
  ========================================================= */

  const [repositoryPath, setRepositoryPath] =
    useState<string | null>(null);

  const [repositoryName, setRepositoryName] =
    useState<string | null>(null);

  const [entries, setEntries] =
    useState<FileSystemEntry[]>([]);

  const [expandedPaths, setExpandedPaths] =
    useState<Set<string>>(new Set());

  const [, setActiveFile] =
    useState<string | null>(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [refreshEpoch, setRefreshEpoch] =
    useState(0);

  /* =========================================================
     OPEN REPOSITORY
  ========================================================= */

  const openRepositoryFromExplorer =
    async () => {
      try {
        setLoading(true);
        setError(null);

        const selectedPath =
          await openRepository();

        /*
         * User cancelled the folder picker.
         */
        if (!selectedPath) {
          return;
        }

        /*
         * Read repository root.
         */
        await window.electronAPI.ensureOutputs(
          selectedPath,
        );

        const rootEntries =
          await readDirectory(selectedPath);

        /*
         * Get repository name.
         */
        const normalizedPath =
          selectedPath.replace(
            /[\\/]+$/,
            "",
          );

        const name =
          normalizedPath.split(/[\\/]/).pop() ||
          "Repository";

        /*
         * Update state.
         */
        setRepositoryPath(selectedPath);
        setRepositoryName(name);
        setEntries(rootEntries);

        repositoryStore.setRepository(
          selectedPath,
        );

        window.dispatchEvent(
          new CustomEvent(
            "testforge:repository-opened",
            {
              detail: {
                repositoryPath:
                  selectedPath,
              },
            },
          ),
        );

        setExpandedPaths(new Set());
        setActiveFile(null);

        /*
         * Notify parent.
         */
        onRepositoryOpened?.(
          selectedPath,
        );
      } catch (err) {
        console.error(
          "Failed to open repository:",
          err,
        );

        setError(
          "Unable to open repository.",
        );
      } finally {
        setLoading(false);
      }
    };

  /* =========================================================
     OPEN REPOSITORY EVENT
  ========================================================= */

  useEffect(() => {
    const handleOpenRepositoryEvent =
      () => {
        void openRepositoryFromExplorer();
      };

    window.addEventListener(
      "testforge:open-repository",
      handleOpenRepositoryEvent,
    );

    return () => {
      window.removeEventListener(
        "testforge:open-repository",
        handleOpenRepositoryEvent,
      );
    };
  }, []);

  /* =========================================================
     LOAD OPENED WORKSPACE
  ========================================================= */

  useEffect(() => {
    const loadOpenedWorkspace =
      async (event: Event) => {
        const path = (
          event as CustomEvent<{
            repositoryPath?: string;
          }>
        ).detail?.repositoryPath;

        if (
          !path ||
          path === repositoryPath
        ) {
          return;
        }

        setLoading(true);
        setError(null);

        try {
          await window.electronAPI.ensureOutputs(
            path,
          );

          const rootEntries =
            await readDirectory(path);

          setRepositoryPath(path);

          setRepositoryName(
            path
              .replace(/[\\/]+$/, "")
              .split(/[\\/]/)
              .pop() ?? "Workspace",
          );

          setEntries(rootEntries);
          setExpandedPaths(new Set());

          setRefreshEpoch(
            (value) => value + 1,
          );
        } catch (err) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to open workspace.",
          );
        } finally {
          setLoading(false);
        }
      };

    window.addEventListener(
      "testforge:repository-opened",
      loadOpenedWorkspace,
    );

    return () => {
      window.removeEventListener(
        "testforge:repository-opened",
        loadOpenedWorkspace,
      );
    };
  }, [repositoryPath]);

  /* =========================================================
     TOGGLE DIRECTORY
  ========================================================= */

  const handleToggle = (
    entry: FileSystemEntry,
  ) => {
    setExpandedPaths((previous) => {
      const next = new Set(previous);

      if (next.has(entry.path)) {
        next.delete(entry.path);
      } else {
        next.add(entry.path);
      }

      return next;
    });
  };

  /* =========================================================
     OPEN FILE
  ========================================================= */

  const handleFileOpen = (
    entry: FileSystemEntry,
  ) => {
    if (entry.type !== "file") {
      return;
    }

    setActiveFile(entry.path);

    /*
     * Preserve the existing parent callback.
     */
    onFileOpen?.(entry.path);

    /*
     * Open the real file in Monaco Editor.
     *
     * Editor.tsx listens for this event,
     * reads the actual file from disk,
     * and creates/activates an editor tab.
     */
    window.dispatchEvent(
      new CustomEvent(
        "testforge:open-file",
        {
          detail: {
            path: entry.path,
            name: entry.name,
          },
        },
      ),
    );
  };

  /* =========================================================
     REFRESH
  ========================================================= */

  const handleRefresh = async () => {
    if (!repositoryPath) {
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const rootEntries =
        await readDirectory(
          repositoryPath,
        );

      setEntries(rootEntries);

      setRefreshEpoch(
        (value) => value + 1,
      );
    } catch (err) {
      console.error(
        "Failed to refresh repository:",
        err,
      );

      setError(
        "Unable to refresh repository.",
      );
    } finally {
      setLoading(false);
    }
  };

  /* =========================================================
     WORKSPACE REFRESH EVENT
  ========================================================= */

  useEffect(() => {
    const refreshWorkspace =
      () => void handleRefresh();

    window.addEventListener(
      "testforge:workspace-refresh",
      refreshWorkspace,
    );

    return () => {
      window.removeEventListener(
        "testforge:workspace-refresh",
        refreshWorkspace,
      );
    };
  }, [repositoryPath]);

  /* =========================================================
     CREATE FILE / FOLDER
  ========================================================= */

  const createEntry = async (
    directory: string,
    isDirectory: boolean,
  ) => {
    const name = window.prompt(
      isDirectory
        ? "New folder name"
        : "New file name",
    );

    if (!name?.trim()) {
      return;
    }

    try {
      const separator =
        directory.includes("\\")
          ? "\\"
          : "/";

      const destination =
        `${directory.replace(
          /[\\/]+$/,
          "",
        )}${separator}${name.trim()}`;

      if (isDirectory) {
        await window.electronAPI.createDirectory(
          destination,
        );
      } else {
        await window.electronAPI.createFile(
          destination,
        );
      }

      await handleRefresh();
    } catch (err) {
      window.alert(
        err instanceof Error
          ? err.message
          : "Unable to create item.",
      );
    }
  };

  /* =========================================================
     RENAME / DELETE
  ========================================================= */

  const handleEntryAction = async (
    entry: FileSystemEntry,
    action: "rename" | "delete",
  ) => {
    if (action === "delete") {
      if (
        !window.confirm(
          `Delete ${entry.name}? This cannot be undone.`,
        )
      ) {
        return;
      }

      try {
        await window.electronAPI.deletePath(
          entry.path,
        );

        await handleRefresh();
      } catch (err) {
        window.alert(
          err instanceof Error
            ? err.message
            : "Unable to delete item.",
        );
      }

      return;
    }

    const name = window.prompt(
      "Rename item",
      entry.name,
    );

    if (
      !name?.trim() ||
      name === entry.name
    ) {
      return;
    }

    const destination =
      `${entry.path.slice(
        0,
        entry.path.length -
          entry.name.length,
      )}${name.trim()}`;

    try {
      await window.electronAPI.renamePath(
        entry.path,
        destination,
      );

      await handleRefresh();
    } catch (err) {
      window.alert(
        err instanceof Error
          ? err.message
          : "Unable to rename item.",
      );
    }
  };

  /* =========================================================
     CLOSE / CLEAR REPOSITORY
  ========================================================= */

  const clearRepository = () => {
    setRepositoryPath(null);
    setRepositoryName(null);
    setEntries([]);
    setExpandedPaths(new Set());
    setActiveFile(null);
    setError(null);

    repositoryStore.clearRepository();

    window.dispatchEvent(
      new CustomEvent(
        "testforge:workspace-closed",
      ),
    );
  };

  /* =========================================================
     RENDER
  ========================================================= */

  return (
    <aside className="flex h-full min-h-0 min-w-0 flex-col border-r border-[#252a33] bg-[#0d1117]">
      {/* =====================================================
          HEADER
      ===================================================== */}

      <div className="flex h-10 shrink-0 items-center border-b border-[#1d222a] px-3">
        <span className="text-[11px] font-semibold tracking-wide text-[#8b949e]">
          EXPLORER
        </span>

        <div className="ml-auto flex items-center gap-1">
          {/* Refresh */}

          {repositoryPath && (
            <button
              type="button"
              title="Refresh Explorer"
              onClick={() =>
                void handleRefresh()
              }
              disabled={loading}
              className="rounded p-1 text-[#8b949e] transition-colors hover:bg-[#21262d] hover:text-white disabled:opacity-50"
            >
              <RefreshCw
                size={14}
                className={
                  loading
                    ? "animate-spin"
                    : ""
                }
              />
            </button>
          )}

          {/* Open Repository */}

          <button
            type="button"
            title="Open Repository"
            onClick={() =>
              void openRepositoryFromExplorer()
            }
            disabled={loading}
            className="rounded p-1 text-[#8b949e] transition-colors hover:bg-[#21262d] hover:text-white disabled:opacity-50"
          >
            <FolderPlus size={15} />
          </button>

          {/* New File */}

          {repositoryPath && (
            <button
              type="button"
              title="New File"
              onClick={() =>
                void createEntry(
                  repositoryPath,
                  false,
                )
              }
              className="rounded p-1 text-[#8b949e] hover:bg-[#21262d] hover:text-white"
            >
              <FilePlus2 size={14} />
            </button>
          )}

          {/* New Folder */}

          {repositoryPath && (
            <button
              type="button"
              title="New Folder"
              onClick={() =>
                void createEntry(
                  repositoryPath,
                  true,
                )
              }
              className="rounded p-1 text-[#8b949e] hover:bg-[#21262d] hover:text-white"
            >
              <FolderPlus size={14} />
            </button>
          )}
        </div>
      </div>

      {/* =====================================================
          CONTENT
      ===================================================== */}

      <div className="min-h-0 flex-1 overflow-y-auto">
        {/* ---------------------------------------------------
            NO REPOSITORY
        --------------------------------------------------- */}

        {!repositoryPath && (
          <div className="flex h-full flex-col items-center justify-center px-5 text-center">
            <FolderOpen
              size={40}
              strokeWidth={1.4}
              className="mb-3 text-[#484f58]"
            />

            <p className="text-xs text-[#8b949e]">
              No repository opened
            </p>

            <p className="mt-1 max-w-[180px] text-[10px] leading-4 text-[#484f58]">
              Open a local project to explore
              its files and folders.
            </p>

            <button
              type="button"
              onClick={() =>
                void openRepositoryFromExplorer()
              }
              disabled={loading}
              className="mt-4 flex items-center gap-2 rounded-md bg-blue-600 px-3 py-1.5 text-[11px] text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading && (
                <Loader2
                  size={12}
                  className="animate-spin"
                />
              )}

              {loading
                ? "Opening..."
                : "Open Repository"}
            </button>

            {error && (
              <div className="mt-3 flex max-w-[200px] items-start gap-2 rounded-md border border-red-500/20 bg-red-500/5 p-2 text-left text-[10px] text-red-400">
                <AlertCircle
                  size={13}
                  className="mt-0.5 shrink-0"
                />

                <span>{error}</span>
              </div>
            )}
          </div>
        )}

        {/* ---------------------------------------------------
            REPOSITORY OPENED
        --------------------------------------------------- */}

        {repositoryPath && (
          <>
            {/* Repository Header */}

            <div className="flex h-8 items-center gap-1 border-b border-[#1d222a] px-2 text-[11px] font-semibold text-[#d7dae0]">
              <ChevronDown
                size={14}
                className="shrink-0 text-[#8b949e]"
              />

              <FolderOpen
                size={14}
                className="shrink-0 text-blue-400"
              />

              <span className="min-w-0 flex-1 truncate">
                {repositoryName}
              </span>
            </div>

            {/* Error */}

            {error && (
              <div className="m-2 flex items-start gap-2 rounded-md border border-red-500/20 bg-red-500/5 p-2 text-[10px] text-red-400">
                <AlertCircle
                  size={13}
                  className="mt-0.5 shrink-0"
                />

                <span>{error}</span>
              </div>
            )}

            {/* Loading */}

            {loading && (
              <div className="flex items-center gap-2 px-4 py-3 text-[11px] text-[#6e7681]">
                <Loader2
                  size={13}
                  className="animate-spin"
                />

                Loading repository...
              </div>
            )}

            {/* Empty repository */}

            {!loading &&
              entries.length === 0 && (
                <div className="px-4 py-3 text-[11px] text-[#6e7681]">
                  This repository is empty.
                </div>
              )}

            {/* File Tree */}

            {!loading &&
              entries.length > 0 && (
                <div className="py-1">
                  <FileTree
                    key={refreshEpoch}
                    entries={entries}
                    expandedPaths={
                      expandedPaths
                    }
                    onToggle={handleToggle}
                    onFileOpen={
                      handleFileOpen
                    }
                    onEntryAction={
                      handleEntryAction
                    }
                  />
                </div>
              )}
          </>
        )}
      </div>

      {/* =====================================================
          FOOTER
      ===================================================== */}

      <div className="flex h-8 shrink-0 items-center border-t border-[#252a33] px-3">
        {repositoryPath ? (
          <div className="flex min-w-0 flex-1 items-center justify-between gap-2">
            <span className="truncate text-[10px] text-[#6e7681]">
              {entries.length}{" "}
              {entries.length === 1
                ? "item"
                : "items"}
            </span>

            <button
              type="button"
              title="Close Repository"
              onClick={clearRepository}
              className="text-[10px] text-[#6e7681] hover:text-white"
            >
              Close
            </button>
          </div>
        ) : (
          <span className="text-[10px] text-[#6e7681]">
            No repository
          </span>
        )}
      </div>
    </aside>
  );
}