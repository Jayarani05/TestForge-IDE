import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import EditorMonaco, {
  type OnMount,
} from "@monaco-editor/react";

import {
  Circle,
  FileCode2,
  FileJson,
  FileText,
  Save,
  X,
} from "lucide-react";

import {
  editorStore,
  useEditorStore,
  type EditorTab,
} from "../stores/editorStore";

import {
  readFile,
  saveFile,
} from "../../services/fileSystem";

interface EditorProps {
  filePath?: string | null;
  fileName?: string | null;
  content?: string;
  language?: string;
  readOnly?: boolean;
  onChange?: (
    value: string,
  ) => void;
  onSave?: (
    path: string,
    content: string,
  ) => Promise<void> | void;

  [key: string]: unknown;
}

interface FileOpenDetail {
  path: string;
  name?: string;
  language?: string;
}

export default function Editor(
  _props: EditorProps,
) {
  const {
    tabs,
    activeTabId,
  } = useEditorStore();

  const activeTab =
    tabs.find(
      (tab) =>
        tab.id === activeTabId,
    ) ?? null;

  const editorRef =
    useRef<unknown>(null);

  const [isSaving, setIsSaving] =
    useState(false);

  const [saveError, setSaveError] =
    useState<string | null>(
      null,
    );

  const [cursorPosition, setCursorPosition] =
    useState({
      line: 1,
      column: 1,
    });

  /*
   * Open files requested by the Explorer.
   */
  useEffect(() => {
    const handleOpenFile = async (
      event: Event,
    ) => {
      const customEvent =
        event as CustomEvent<FileOpenDetail>;

      const detail =
        customEvent.detail;

      if (
        !detail?.path
      ) {
        return;
      }

      try {
        const content =
          await readFile(
            detail.path,
          );

        editorStore.openFile({
          id: detail.path,
          path: detail.path,
          name:
            detail.name ??
            getFileName(
              detail.path,
            ),
          language:
            detail.language ??
            detectLanguage(
              detail.path,
            ),
          content,
          savedContent:
            content,
          isDirty: false,
        });
      } catch (error) {
        console.error(
          "TestForge Editor could not open file:",
          error,
        );
      }
    };

    window.addEventListener(
      "testforge:open-file",
      handleOpenFile,
    );

    return () => {
      window.removeEventListener(
        "testforge:open-file",
        handleOpenFile,
      );
    };
  }, []);

  /*
   * Support Ctrl+S globally.
   */
  useEffect(() => {
    const handleKeyboard =
      (event: KeyboardEvent) => {
        if (
          (event.ctrlKey ||
            event.metaKey) &&
          event.key.toLowerCase() ===
            "s"
        ) {
          event.preventDefault();

          void saveActiveFile();
        }
      };

    window.addEventListener(
      "keydown",
      handleKeyboard,
    );

    return () => {
      window.removeEventListener(
        "keydown",
        handleKeyboard,
      );
    };
  }, [activeTabId, tabs]);

  /*
   * Save active editor file.
   */
  const saveActiveFile =
    useCallback(
      async () => {
        if (
          !activeTab ||
          !activeTab.isDirty
        ) {
          return;
        }

        setIsSaving(true);
        setSaveError(null);

        try {
          await saveFile(
            activeTab.path,
            activeTab.content,
          );

          editorStore.markSaved(
            activeTab.id,
            activeTab.content,
          );

          window.dispatchEvent(
            new CustomEvent(
              "testforge:file-saved",
              {
                detail: {
                  path:
                    activeTab.path,
                },
              },
            ),
          );
        } catch (error) {
          const message =
            error instanceof Error
              ? error.message
              : "Unable to save file.";

          setSaveError(
            message,
          );

          console.error(
            "TestForge Editor save failed:",
            error,
          );
        } finally {
          setIsSaving(false);
        }
      },
      [activeTab],
    );

  /*
   * Monaco mount.
   */
  const handleEditorMount: OnMount =
    (editor) => {
      editorRef.current =
        editor;

      editor.onDidChangeCursorPosition(
        (event) => {
          setCursorPosition({
            line:
              event.position
                .lineNumber,
            column:
              event.position
                .column,
          });
        },
      );

      editor.addCommand(
        2048 | 49,
        () => {
          void saveActiveFile();
        },
      );
    };

  /*
   * Monaco content change.
   */
  const handleChange = (
    value: string | undefined,
  ) => {
    if (
      !activeTab ||
      value === undefined
    ) {
      return;
    }

    editorStore.updateContent(
      activeTab.id,
      value,
    );

    window.dispatchEvent(
      new CustomEvent(
        "testforge:file-changed",
        {
          detail: {
            path:
              activeTab.path,
            content: value,
          },
        },
      ),
    );
  };

  /*
   * Empty state.
   */
  if (!activeTab) {
    return (
      <div className="flex h-full min-h-0 flex-col bg-[#0d1117] text-[#8b949e]">
        <div className="flex h-9 shrink-0 items-center border-b border-[#252a33] bg-[#11161d] px-3">
          <span className="text-[10px] uppercase tracking-wide text-[#6e7681]">
            Editor
          </span>
        </div>

        <div className="flex min-h-0 flex-1 items-center justify-center">
          <div className="max-w-sm text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl border border-[#30363d] bg-[#161b22]">
              <FileCode2
                size={26}
                className="text-blue-400"
              />
            </div>

            <h2 className="text-[14px] font-semibold text-[#c9d1d9]">
              TestForge IDE
            </h2>

            <p className="mt-2 text-[11px] leading-5 text-[#6e7681]">
              Open a file from the
              Explorer to start
              editing source code or
              generated automation.
            </p>

            <div className="mt-4 rounded-md border border-[#252a33] bg-[#11161d] px-3 py-2 text-left">
              <p className="text-[9px] text-[#6e7681]">
                SHORTCUT
              </p>

              <p className="mt-1 text-[10px] text-[#c9d1d9]">
                Ctrl + S
                <span className="ml-2 text-[#6e7681]">
                  Save current file
                </span>
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col bg-[#0d1117] text-[#c9d1d9]">
      {/* TAB BAR */}

      <div className="flex h-9 shrink-0 items-stretch overflow-x-auto border-b border-[#252a33] bg-[#11161d]">
        {tabs.map((tab) => (
          <EditorTabButton
            key={tab.id}
            tab={tab}
            active={
              tab.id ===
              activeTabId
            }
            onActivate={() =>
              editorStore.activateTab(
                tab.id,
              )
            }
            onClose={() =>
              editorStore.closeTab(
                tab.id,
              )
            }
          />
        ))}

        <div className="flex min-w-0 flex-1 items-center justify-end px-2">
          {activeTab.isDirty && (
            <button
              type="button"
              title="Save"
              onClick={() =>
                void saveActiveFile()
              }
              disabled={isSaving}
              className="mr-1 flex h-7 w-7 items-center justify-center rounded text-[#8b949e] hover:bg-[#21262d] hover:text-white disabled:opacity-50"
            >
              <Save
                size={13}
              />
            </button>
          )}

          <button
            type="button"
            title="Close all editors"
            onClick={() =>
              editorStore.closeAll()
            }
            className="flex h-7 w-7 items-center justify-center rounded text-[#6e7681] hover:bg-[#21262d] hover:text-white"
          >
            <X
              size={13}
            />
          </button>
        </div>
      </div>

      {/* BREADCRUMB */}

      <div className="flex h-7 shrink-0 items-center gap-1 border-b border-[#1f252d] bg-[#0d1117] px-3 text-[9px] text-[#6e7681]">
        {getPathSegments(
          activeTab.path,
        ).map(
          (
            segment,
            index,
          ) => (
            <span
              key={`${segment}-${index}`}
              className={
                index ===
                getPathSegments(
                  activeTab.path,
                ).length -
                  1
                  ? "font-medium text-[#c9d1d9]"
                  : ""
              }
            >
              {segment}
              {index <
                getPathSegments(
                  activeTab.path,
                ).length -
                  1 && (
                <span className="mx-1 text-[#484f58]">
                  /
                </span>
              )}
            </span>
          ),
        )}
      </div>

      {/* EDITOR */}

      <div className="min-h-0 flex-1">
        <EditorMonaco
          path={activeTab.path}
          value={
            activeTab.content
          }
          language={
            monacoLanguage(
              activeTab.language,
            )
          }
          theme="testforge-dark"
          onMount={
            handleEditorMount
          }
          onChange={
            handleChange
          }
          options={{
            automaticLayout: true,
            minimap: {
              enabled: true,
            },
            fontSize: 13,
            lineHeight: 20,
            fontLigatures: true,
            smoothScrolling: true,
            scrollBeyondLastLine: false,
            renderWhitespace:
              "selection",
            bracketPairColorization: {
              enabled: true,
            },
            guides: {
              indentation: true,
            },
            wordWrap: "off",
            padding: {
              top: 12,
              bottom: 12,
            },
            suggest: {
              showMethods: true,
              showFunctions: true,
              showConstructors: true,
              showClasses: true,
              showModules: true,
              showVariables: true,
            },
          }}
          beforeMount={(monaco) => {
            monaco.editor.defineTheme(
              "testforge-dark",
              {
                base: "vs-dark",
                inherit: true,
                rules: [
                  {
                    token:
                      "comment",
                    foreground:
                      "6A737D",
                  },
                  {
                    token:
                      "keyword",
                    foreground:
                      "C586C0",
                  },
                  {
                    token:
                      "string",
                    foreground:
                      "CE9178",
                  },
                  {
                    token:
                      "number",
                    foreground:
                      "B5CEA8",
                  },
                  {
                    token:
                      "type",
                    foreground:
                      "4EC9B0",
                  },
                ],
                colors: {
                  "editor.background":
                    "#0D1117",
                  "editor.foreground":
                    "#C9D1D9",
                  "editorLineNumber.foreground":
                    "#484F58",
                  "editorLineNumber.activeForeground":
                    "#C9D1D9",
                  "editorCursor.foreground":
                    "#58A6FF",
                  "editor.selectionBackground":
                    "#264F78",
                  "editor.lineHighlightBackground":
                    "#161B22",
                  "editorIndentGuide.background":
                    "#21262D",
                  "editorIndentGuide.activeBackground":
                    "#30363D",
                  "editorWidget.background":
                    "#161B22",
                  "editorWidget.border":
                    "#30363D",
                },
              },
            );
          }}
        />
      </div>

      {/* SAVE / STATUS */}

      <div className="flex h-6 shrink-0 items-center border-t border-[#252a33] bg-[#11161d] px-3 text-[9px]">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          {activeTab.isDirty ? (
            <span className="flex items-center gap-1 text-yellow-400">
              <Circle
                size={6}
                fill="currentColor"
              />
              Unsaved Changes
            </span>
          ) : (
            <span className="text-emerald-400">
              Saved
            </span>
          )}

          {isSaving && (
            <span className="text-[#8b949e]">
              Saving...
            </span>
          )}

          {saveError && (
            <span className="truncate text-red-400">
              {saveError}
            </span>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-3 text-[#8b949e]">
          <span>
            Ln{" "}
            {
              cursorPosition.line
            }
            , Col{" "}
            {
              cursorPosition.column
            }
          </span>

          <span>
            {activeTab.language}
          </span>

          <span>
            UTF-8
          </span>

          <span>
            LF
          </span>
        </div>
      </div>
    </div>
  );
}

/* ========================================================================== */
/* TAB                                                                       */
/* ========================================================================== */

function EditorTabButton({
  tab,
  active,
  onActivate,
  onClose,
}: {
  tab: EditorTab;
  active: boolean;
  onActivate: () => void;
  onClose: () => void;
}) {
  return (
    <div
      className={`group flex h-full max-w-[220px] min-w-[130px] items-center border-r border-[#252a33] ${
        active
          ? "bg-[#0d1117]"
          : "bg-[#11161d]"
      }`}
    >
      <button
        type="button"
        onClick={
          onActivate
        }
        className="flex min-w-0 flex-1 items-center gap-2 px-3 text-left"
      >
        <FileTypeIcon
          name={tab.name}
        />

        <span
          className={`min-w-0 flex-1 truncate text-[10px] ${
            active
              ? "text-[#f0f6fc]"
              : "text-[#8b949e]"
          }`}
        >
          {tab.name}
        </span>

        {tab.isDirty && (
          <Circle
            size={7}
            fill="currentColor"
            className="shrink-0 text-[#c9d1d9]"
          />
        )}
      </button>

      <button
        type="button"
        title="Close"
        onClick={
          onClose
        }
        className="mr-1 flex h-6 w-6 shrink-0 items-center justify-center rounded text-[#6e7681] opacity-0 transition-opacity hover:bg-[#21262d] hover:text-white group-hover:opacity-100"
      >
        <X
          size={12}
        />
      </button>
    </div>
  );
}

/* ========================================================================== */
/* ICON                                                                       */
/* ========================================================================== */

function FileTypeIcon({
  name,
}: {
  name: string;
}) {
  const extension =
    name
      .split(".")
      .pop()
      ?.toLowerCase();

  if (
    extension ===
      "json" ||
    extension ===
      "jsonc"
  ) {
    return (
      <FileJson
        size={13}
        className="shrink-0 text-yellow-400"
      />
    );
  }

  if (
    extension ===
      "md" ||
    extension ===
      "txt"
  ) {
    return (
      <FileText
        size={13}
        className="shrink-0 text-[#8b949e]"
      />
    );
  }

  return (
    <FileCode2
      size={13}
      className="shrink-0 text-blue-400"
    />
  );
}

/* ========================================================================== */
/* LANGUAGE                                                                   */
/* ========================================================================== */

function detectLanguage(
  path: string,
) {
  const extension =
    path
      .split(".")
      .pop()
      ?.toLowerCase();

  const languages: Record<
    string,
    string
  > = {
    ts: "TypeScript",
    tsx: "TypeScript React",
    js: "JavaScript",
    jsx: "JavaScript React",
    py: "Python",
    java: "Java",
    kt: "Kotlin",
    cs: "C#",
    cpp: "C++",
    c: "C",
    go: "Go",
    rs: "Rust",
    php: "PHP",
    rb: "Ruby",
    swift: "Swift",
    xml: "XML",
    html: "HTML",
    css: "CSS",
    scss: "SCSS",
    json: "JSON",
    yaml: "YAML",
    yml: "YAML",
    md: "Markdown",
    sql: "SQL",
    sh: "Shell",
    ps1: "PowerShell",
    dockerfile:
      "Dockerfile",
  };

  return (
    languages[
      extension ?? ""
    ] ?? "Plain Text"
  );
}

function monacoLanguage(
  language: string,
) {
  const normalized =
    language.toLowerCase();

  const languages: Record<
    string,
    string
  > = {
    typescript:
      "typescript",
    "typescript react":
      "typescript",
    javascript:
      "javascript",
    "javascript react":
      "javascript",
    python: "python",
    java: "java",
    kotlin: "kotlin",
    "c#": "csharp",
    "c++": "cpp",
    c: "c",
    go: "go",
    rust: "rust",
    php: "php",
    ruby: "ruby",
    swift: "swift",
    xml: "xml",
    html: "html",
    css: "css",
    scss: "scss",
    json: "json",
    yaml: "yaml",
    markdown:
      "markdown",
    sql: "sql",
    shell: "shell",
    powershell:
      "powershell",
    dockerfile:
      "dockerfile",
    "plain text":
      "plaintext",
  };

  return (
    languages[
      normalized
    ] ?? "plaintext"
  );
}

function getFileName(
  path: string,
) {
  return (
    path.split(/[\\/]/).pop() ??
    path
  );
}

function getPathSegments(
  path: string,
) {
  return path
    .split(/[\\/]/)
    .filter(Boolean)
    .slice(-5);
}