import { useEffect, useRef, useState } from "react";

interface TopBarProps {
  showExplorer: boolean;
  showAI: boolean;
  showBottomPanel: boolean;

  onToggleExplorer: () => void;
  onToggleAI: () => void;
  onToggleBottomPanel: () => void;

  onOpenRepository: () => void;
  onSave: () => void;
  onCloseWorkspace: () => void;
  onExit: () => void;

  onRunTests: () => void;
  onRunCurrentTest: () => void;
  onDebugTests: () => void;

  onClearTerminal: () => void;
  onNewTerminal: () => void;

  onShowWelcome: () => void;
  onFocusExplorer: () => void;
  onFocusAI: () => void;

  onAbout: () => void;
}

type MenuName =
  | "File"
  | "Edit"
  | "Selection"
  | "View"
  | "Go"
  | "Run"
  | "Terminal"
  | "Help"
  | null;

interface MenuItem {
  label?: string;
  shortcut?: string;
  separator?: boolean;
  disabled?: boolean;
  submenu?: boolean;
  onClick?: () => void;
}

export default function TopBar({
  showExplorer,
  showAI,
  showBottomPanel,
  onToggleExplorer,
  onToggleAI,
  onToggleBottomPanel,
  onOpenRepository,
  onSave,
  onCloseWorkspace,
  onExit,
  onRunTests,
  onRunCurrentTest,
  onDebugTests,
  onClearTerminal,
  onNewTerminal,
  onShowWelcome,
  onFocusExplorer,
  onFocusAI,
  onAbout,
}: TopBarProps) {
  const [activeMenu, setActiveMenu] =
    useState<MenuName>(null);

  const menuBarRef =
    useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (
      event: MouseEvent,
    ) => {
      if (
        menuBarRef.current &&
        !menuBarRef.current.contains(
          event.target as Node,
        )
      ) {
        setActiveMenu(null);
      }
    };

    document.addEventListener(
      "mousedown",
      handleOutsideClick,
    );

    return () => {
      document.removeEventListener(
        "mousedown",
        handleOutsideClick,
      );
    };
  }, []);

  const closeMenu = () => {
    setActiveMenu(null);
  };

  const runCommand = (
    callback?: () => void,
  ) => {
    closeMenu();
    callback?.();
  };

  const fileItems: MenuItem[] = [
    {
      label: "New Text File",
      shortcut: "Ctrl+N",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:new-file",
          ),
        );
      },
    },
    {
      label: "New Window",
      shortcut: "Ctrl+Shift+N",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:new-window",
          ),
        );
      },
    },
    {
      separator: true,
    },
    {
      label: "Open File...",
      shortcut: "Ctrl+O",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:open-file",
          ),
        );
      },
    },
    {
      label: "Open Folder...",
      shortcut: "Ctrl+K Ctrl+O",
      onClick: onOpenRepository,
    },
    {
      label: "Open Workspace from File...",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:open-workspace",
          ),
        );
      },
    },
    {
      separator: true,
    },
    {
      label: "Add Folder to Workspace...",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:add-folder",
          ),
        );
      },
    },
    {
      separator: true,
    },
    {
      label: "Save",
      shortcut: "Ctrl+S",
      onClick: onSave,
    },
    {
      label: "Save As...",
      shortcut: "Ctrl+Shift+S",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:save-as",
          ),
        );
      },
    },
    {
      label: "Save All",
      shortcut: "Ctrl+K S",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:save-all",
          ),
        );
      },
    },
    {
      separator: true,
    },
    {
      label: "Auto Save",
      submenu: true,
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:auto-save",
          ),
        );
      },
    },
    {
      label: "Preferences",
      submenu: true,
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:preferences",
          ),
        );
      },
    },
    {
      separator: true,
    },
    {
      label: "Close Editor",
      shortcut: "Ctrl+W",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:close-editor",
          ),
        );
      },
    },
    {
      label: "Close Folder",
      onClick: onCloseWorkspace,
    },
    {
      label: "Close Window",
      shortcut: "Ctrl+Shift+W",
      onClick: () => {
        window.close();
      },
    },
    {
      separator: true,
    },
    {
      label: "Exit",
      onClick: onExit,
    },
  ];

  const editItems: MenuItem[] = [
    {
      label: "Undo",
      shortcut: "Ctrl+Z",
      onClick: () =>
        document.execCommand("undo"),
    },
    {
      label: "Redo",
      shortcut: "Ctrl+Y",
      onClick: () =>
        document.execCommand("redo"),
    },
    {
      separator: true,
    },
    {
      label: "Cut",
      shortcut: "Ctrl+X",
      onClick: () =>
        document.execCommand("cut"),
    },
    {
      label: "Copy",
      shortcut: "Ctrl+C",
      onClick: () =>
        document.execCommand("copy"),
    },
    {
      label: "Paste",
      shortcut: "Ctrl+V",
      onClick: () =>
        document.execCommand("paste"),
    },
    {
      separator: true,
    },
    {
      label: "Find",
      shortcut: "Ctrl+F",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:find",
          ),
        );
      },
    },
    {
      label: "Replace",
      shortcut: "Ctrl+H",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:replace",
          ),
        );
      },
    },
  ];

  const selectionItems: MenuItem[] = [
    {
      label: "Select All",
      shortcut: "Ctrl+A",
      onClick: () =>
        document.execCommand(
          "selectAll",
        ),
    },
    {
      separator: true,
    },
    {
      label: "Expand Selection",
      shortcut: "Shift+Alt+Right",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:expand-selection",
          ),
        );
      },
    },
    {
      label: "Shrink Selection",
      shortcut: "Shift+Alt+Left",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:shrink-selection",
          ),
        );
      },
    },
  ];

  const viewItems: MenuItem[] = [
    {
      label: "Explorer",
      shortcut: "Ctrl+Shift+E",
      onClick: onToggleExplorer,
    },
    {
      label: "TestForge AI",
      shortcut: "Ctrl+Shift+A",
      onClick: onToggleAI,
    },
    {
      label: "Bottom Panel",
      shortcut: "Ctrl+J",
      onClick: onToggleBottomPanel,
    },
    {
      separator: true,
    },
    {
      label: "Appearance",
      submenu: true,
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:appearance",
          ),
        );
      },
    },
    {
      separator: true,
    },
    {
      label: "Reset Layout",
      onClick: () => {
        onToggleExplorer();
        onToggleAI();
        onToggleBottomPanel();
      },
    },
  ];

  const goItems: MenuItem[] = [
    {
      label: "Back",
      shortcut: "Alt+Left",
      disabled: true,
    },
    {
      label: "Forward",
      shortcut: "Alt+Right",
      disabled: true,
    },
    {
      separator: true,
    },
    {
      label: "Welcome",
      onClick: onShowWelcome,
    },
    {
      label: "Explorer",
      shortcut: "Ctrl+Shift+E",
      onClick: onFocusExplorer,
    },
    {
      label: "TestForge AI",
      onClick: onFocusAI,
    },
  ];

  const runItems: MenuItem[] = [
    {
      label: "Run Tests",
      shortcut: "Ctrl+F5",
      onClick: onRunTests,
    },
    {
      label: "Run Current Test",
      shortcut: "Ctrl+F6",
      onClick: onRunCurrentTest,
    },
    {
      label: "Debug Tests",
      shortcut: "F5",
      onClick: onDebugTests,
    },
    {
      separator: true,
    },
    {
      label: "Generate Tests",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:generate-tests",
          ),
        );
      },
    },
    {
      label: "Analyze Failure",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:analyze-failure",
          ),
        );
      },
    },
    {
      label: "Self-Heal Test",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:self-heal",
          ),
        );
      },
    },
    {
      separator: true,
    },
    {
      label: "Test Analytics",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:analytics",
          ),
        );
      },
    },
  ];

  const terminalItems: MenuItem[] = [
    {
      label: "New Terminal",
      shortcut: "Ctrl+Shift+`",
      onClick: onNewTerminal,
    },
    {
      separator: true,
    },
    {
      label: "Clear Terminal",
      onClick: onClearTerminal,
    },
  ];

  const helpItems: MenuItem[] = [
    {
      label: "Documentation",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:documentation",
          ),
        );
      },
    },
    {
      label: "Keyboard Shortcuts",
      shortcut: "Ctrl+K Ctrl+S",
      onClick: () => {
        window.dispatchEvent(
          new CustomEvent(
            "testforge:keyboard-shortcuts",
          ),
        );
      },
    },
    {
      separator: true,
    },
    {
      label: "About TestForge",
      onClick: onAbout,
    },
  ];

  const menus: {
    name: Exclude<MenuName, null>;
    items: MenuItem[];
  }[] = [
    {
      name: "File",
      items: fileItems,
    },
    {
      name: "Edit",
      items: editItems,
    },
    {
      name: "Selection",
      items: selectionItems,
    },
    {
      name: "View",
      items: viewItems,
    },
    {
      name: "Go",
      items: goItems,
    },
    {
      name: "Run",
      items: runItems,
    },
    {
      name: "Terminal",
      items: terminalItems,
    },
    {
      name: "Help",
      items: helpItems,
    },
  ];

  const handleMenuClick = (
    menuName: Exclude<MenuName, null>,
  ) => {
    setActiveMenu((current) =>
      current === menuName
        ? null
        : menuName,
    );
  };

  const handleItemClick = (
    item: MenuItem,
  ) => {
    if (
      item.separator ||
      item.disabled
    ) {
      return;
    }

    runCommand(item.onClick);
  };

  return (
    <header
      ref={menuBarRef}
      className="relative z-50 flex h-9 shrink-0 items-center border-b border-[#252a33] bg-[#0d1117] text-[#c9d1d9]"
    >
      {/* TestForge Logo */}
      <div className="flex h-full w-[52px] shrink-0 items-center justify-center border-r border-[#252a33]">
        <div className="flex h-5 w-5 items-center justify-center rounded bg-blue-600 text-[10px] font-bold text-white">
          TF
        </div>
      </div>

      {/* Menu Bar */}
      <div className="flex h-full items-center">
        {menus.map((menu) => {
          const isOpen =
            activeMenu === menu.name;

          return (
            <div
              key={menu.name}
              className="relative h-full"
            >
              <button
                type="button"
                onClick={() =>
                  handleMenuClick(
                    menu.name,
                  )
                }
                className={`flex h-full items-center px-3 text-[12px] transition-colors ${
                  isOpen
                    ? "bg-[#252a33] text-white"
                    : "text-[#c9d1d9] hover:bg-[#1f242c] hover:text-white"
                }`}
              >
                {menu.name}
              </button>

              {isOpen && (
                <div className="absolute left-0 top-[36px] min-w-[270px] overflow-hidden rounded-md border border-[#30363d] bg-[#161b22] py-1 shadow-2xl">
                  {menu.items.map(
                    (
                      item,
                      index,
                    ) => {
                      if (
                        item.separator
                      ) {
                        return (
                          <div
                            key={`separator-${index}`}
                            className="my-1 border-t border-[#30363d]"
                          />
                        );
                      }

                      return (
                        <button
                          key={`${item.label}-${index}`}
                          type="button"
                          disabled={
                            item.disabled
                          }
                          onClick={() =>
                            handleItemClick(
                              item,
                            )
                          }
                          className={`group flex w-full items-center px-3 py-[5px] text-left text-[12px] ${
                            item.disabled
                              ? "cursor-default text-[#484f58]"
                              : "text-[#c9d1d9] hover:bg-[#094771] hover:text-white"
                          }`}
                        >
                          <span className="min-w-0 flex-1">
                            {item.label}
                          </span>

                          {item.shortcut && (
                            <span className="ml-8 text-[10px] text-[#8b949e] group-hover:text-[#c9d1d9]">
                              {
                                item.shortcut
                              }
                            </span>
                          )}

                          {item.submenu && (
                            <span className="ml-4 text-[#8b949e]">
                              ›
                            </span>
                          )}
                        </button>
                      );
                    },
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Center Title */}
      <div className="pointer-events-none absolute left-1/2 hidden -translate-x-1/2 items-center gap-2 text-[11px] text-[#6e7681] md:flex">
        <span>
          TestForge IDE
        </span>

        <span className="text-[#30363d]">
          —
        </span>

        <span>
          Intelligent Software Testing
        </span>
      </div>

      {/* Right Status */}
      <div className="ml-auto flex h-full items-center px-3">
        <span className="text-[10px] text-[#484f58]">
          {showExplorer &&
            "Explorer"}
          {showExplorer &&
            showAI &&
            " · "}
          {showAI &&
            "AI"}
          {(showExplorer ||
            showAI) &&
            showBottomPanel &&
            " · "}
          {showBottomPanel &&
            "Terminal"}
        </span>
      </div>
    </header>
  );
}