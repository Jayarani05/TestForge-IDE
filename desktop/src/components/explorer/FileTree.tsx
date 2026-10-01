import { useEffect, useState } from "react";

import {
  ChevronDown,
  ChevronRight,
  File,
  FileCode2,
  FileJson,
  FileText,
  Folder,
  FolderOpen,
  Loader2,
} from "lucide-react";

import type { FileSystemEntry } from "../../types/electron";

interface FileTreeProps {
  entries: FileSystemEntry[];
  level?: number;
  expandedPaths: Set<string>;
  onToggle: (entry: FileSystemEntry) => void;
  onFileOpen: (entry: FileSystemEntry) => void;
  onEntryAction?: (
    entry: FileSystemEntry,
    action: "rename" | "delete",
  ) => void;
}

/* =========================================================
   FILE ICON
========================================================= */

function getFileIcon(name: string) {
  const extension = name
    .split(".")
    .pop()
    ?.toLowerCase();

  if (
    extension === "ts" ||
    extension === "tsx" ||
    extension === "js" ||
    extension === "jsx" ||
    extension === "java" ||
    extension === "py" ||
    extension === "c" ||
    extension === "cpp" ||
    extension === "cs"
  ) {
    return (
      <FileCode2
        size={15}
        className="shrink-0 text-yellow-400"
      />
    );
  }

  if (
    extension === "json" ||
    extension === "jsonc" ||
    extension === "xml" ||
    extension === "yaml" ||
    extension === "yml"
  ) {
    return (
      <FileJson
        size={15}
        className="shrink-0 text-yellow-300"
      />
    );
  }

  if (
    extension === "md" ||
    extension === "txt" ||
    extension === "properties"
  ) {
    return (
      <FileText
        size={15}
        className="shrink-0 text-[#8b949e]"
      />
    );
  }

  return (
    <File
      size={15}
      className="shrink-0 text-[#8b949e]"
    />
  );
}

/* =========================================================
   FILE TREE
========================================================= */

export default function FileTree({
  entries,
  level = 0,
  expandedPaths,
  onToggle,
  onFileOpen,
  onEntryAction,
}: FileTreeProps) {
  return (
    <div>
      {entries.map((entry) => {
        const expanded =
          expandedPaths.has(entry.path);

        return (
          <div key={entry.path}>
            <button
              type="button"
              className="group flex h-7 w-full items-center gap-1 text-left text-[12px] text-[#c9d1d9] transition-colors hover:bg-[#161b22]"
              style={{
                paddingLeft: `${
                  8 + level * 16
                }px`,
                paddingRight: "8px",
              }}
              onClick={() => {
                if (
                  entry.type ===
                  "directory"
                ) {
                  onToggle(entry);
                } else {
                  onFileOpen(entry);
                }
              }}
              onContextMenu={(event) => {
                event.preventDefault();

                const action =
                  window.prompt(
                    `Action for ${entry.name}: type rename or delete`,
                  );

                if (
                  action === "rename" ||
                  action === "delete"
                ) {
                  onEntryAction?.(
                    entry,
                    action,
                  );
                }
              }}
            >
              {/* Expand / collapse */}

              {entry.type ===
              "directory" ? (
                expanded ? (
                  <ChevronDown
                    size={14}
                    className="shrink-0 text-[#8b949e]"
                  />
                ) : (
                  <ChevronRight
                    size={14}
                    className="shrink-0 text-[#8b949e]"
                  />
                )
              ) : (
                <span className="w-[14px] shrink-0" />
              )}

              {/* File / folder icon */}

              {entry.type ===
              "directory" ? (
                expanded ? (
                  <FolderOpen
                    size={15}
                    className="shrink-0 text-blue-400"
                  />
                ) : (
                  <Folder
                    size={15}
                    className="shrink-0 text-blue-400"
                  />
                )
              ) : (
                getFileIcon(entry.name)
              )}

              {/* Name */}

              <span className="min-w-0 flex-1 truncate">
                {entry.name}
              </span>
            </button>

            {/* Children */}

            {entry.type ===
              "directory" &&
              expanded && (
                <DirectoryChildren
                  path={entry.path}
                  level={level + 1}
                  expandedPaths={
                    expandedPaths
                  }
                  onToggle={onToggle}
                  onFileOpen={
                    onFileOpen
                  }
                  onEntryAction={
                    onEntryAction
                  }
                />
              )}
          </div>
        );
      })}
    </div>
  );
}

/* =========================================================
   DIRECTORY CHILDREN
========================================================= */

function DirectoryChildren({
  path,
  level,
  expandedPaths,
  onToggle,
  onFileOpen,
  onEntryAction,
}: {
  path: string;
  level: number;
  expandedPaths: Set<string>;
  onToggle: (entry: FileSystemEntry) => void;
  onFileOpen: (entry: FileSystemEntry) => void;
  onEntryAction?: (
    entry: FileSystemEntry,
    action: "rename" | "delete",
  ) => void;
}) {
  const [entries, setEntries] =
    useState<FileSystemEntry[]>(
      [],
    );

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState(false);

  useEffect(() => {
    let cancelled = false;

    const loadDirectory =
      async () => {
        try {
          setLoading(true);
          setError(false);

          const result =
            await window.electronAPI.readDirectory(
              path,
            );

          if (!cancelled) {
            setEntries(result);
          }
        } catch (err) {
          console.error(
            "Failed to read directory:",
            err,
          );

          if (!cancelled) {
            setError(true);
          }
        } finally {
          if (!cancelled) {
            setLoading(false);
          }
        }
      };

    void loadDirectory();

    return () => {
      cancelled = true;
    };
  }, [path]);

  if (loading) {
    return (
      <div
        className="flex h-7 items-center gap-2 text-[11px] text-[#6e7681]"
        style={{
          paddingLeft: `${
            24 + level * 16
          }px`,
        }}
      >
        <Loader2
          size={12}
          className="animate-spin"
        />

        Loading...
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="flex h-7 items-center text-[11px] text-red-400"
        style={{
          paddingLeft: `${
            24 + level * 16
          }px`,
        }}
      >
        Unable to read folder
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div
        className="flex h-7 items-center text-[11px] italic text-[#6e7681]"
        style={{
          paddingLeft: `${
            24 + level * 16
          }px`,
        }}
      >
        Empty folder
      </div>
    );
  }

  return (
    <FileTree
      entries={entries}
      level={level}
      expandedPaths={expandedPaths}
      onToggle={onToggle}
      onFileOpen={onFileOpen}
      onEntryAction={onEntryAction}
    />
  );
}