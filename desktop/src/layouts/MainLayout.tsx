import { useState } from "react";

import TopBar from "../components/top-bar/TopBar";

import ActivityBar, {
  type ActivityView,
} from "../components/activity-bar/ActivityBar";

import ActivityPanel from "../components/activity-panel/ActivityPanel";

import Explorer from "../components/explorer/Explorer";

import Editor from "../components/editor/Editor";

import AIPanel from "../components/ai-panel/AIPanel";

import BottomPanel from "../components/bottom-panel/BottomPanel";

import StatusBar from "../components/status-bar/StatusBar";

import {
  inspectRepository,
  analyzeRepository,
  indexRepositoryContext,
} from "../services/repositoryApi";

import {
  openRepository,
} from "../services/fileSystem";

import {
  repositoryStore,
} from "../components/stores/repositoryStore";

export default function MainLayout() {
  const [activeFile, setActiveFile] =
    useState<string | null>(null);

  /*
   * LEFT SIDEBAR
   */
  const [activeView, setActiveView] =
    useState<ActivityView>("explorer");

  /*
   * RIGHT AI PANEL
   */
  const [showAI, setShowAI] =
    useState(false);

  /*
   * BOTTOM PANEL
   */
  const [showBottomPanel, setShowBottomPanel] =
    useState(true);

  /* ---------------------------------------------------------------------- */
  /* ACTIVITY BAR                                                           */
  /* ---------------------------------------------------------------------- */

  const handleActivityViewChange = (
    view: ActivityView,
  ) => {
    setActiveView(view);
  };

  const handleAIToggle = () => {
    setShowAI((current) => !current);
  };

  /* ---------------------------------------------------------------------- */
  /* FILE                                                                    */
  /* ---------------------------------------------------------------------- */

  const handleOpenRepository = async () => {
    setActiveView("explorer");

    try {
      const repositoryPath = await openRepository();

      if (!repositoryPath) {
        return;
      }

      repositoryStore.setRepository(repositoryPath);
      repositoryStore.setAnalyzing(true);

      window.dispatchEvent(
        new CustomEvent("testforge:repository-opened", {
          detail: {
            repositoryPath,
          },
        }),
      );

      await inspectRepository(repositoryPath);

      const analysis = await analyzeRepository(
        repositoryPath,
      );

      repositoryStore.setAnalysis(analysis);

      await indexRepositoryContext(repositoryPath);

      window.dispatchEvent(
        new CustomEvent("testforge:repository-analyzed", {
          detail: {
              repositoryPath,
          analysis,
          },
       }),
      );
    } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "Repository analysis failed.";

        repositoryStore.setError(message);

        window.dispatchEvent(
          new CustomEvent("testforge:repository-error", {
            detail: {
              message,
            },
          }),
        );

        console.error(
          "TestForge repository workflow failed:",
          error,
        );
      }
    };

  const handleSave = () => {
    window.dispatchEvent(
      new CustomEvent("testforge:save"),
    );

    console.log(
      "Save requested:",
      activeFile,
    );
  };

  const handleCloseWorkspace = () => {
    setActiveFile(null);

    window.dispatchEvent(
      new CustomEvent(
        "testforge:close-workspace",
      ),
    );
  };

  const handleExit = () => {
    window.close();
  };

  /* ---------------------------------------------------------------------- */
  /* RUN                                                                     */
  /* ---------------------------------------------------------------------- */

  const handleRunTests = () => {
    setActiveView("run");
    setShowBottomPanel(true);

    window.dispatchEvent(
      new CustomEvent(
        "testforge:run-tests",
      ),
    );
  };

  const handleRunCurrentTest = () => {
    setActiveView("run");
    setShowBottomPanel(true);

    window.dispatchEvent(
      new CustomEvent(
        "testforge:run-current-test",
      ),
    );
  };

  const handleDebugTests = () => {
    setActiveView("run");
    setShowBottomPanel(true);

    window.dispatchEvent(
      new CustomEvent(
        "testforge:debug-tests",
      ),
    );
  };

  /* ---------------------------------------------------------------------- */
  /* TERMINAL                                                                */
  /* ---------------------------------------------------------------------- */

  const handleClearTerminal = () => {
    window.dispatchEvent(
      new CustomEvent(
        "testforge:clear-terminal",
      ),
    );
  };

  const handleNewTerminal = () => {
    setShowBottomPanel(true);

    window.dispatchEvent(
      new CustomEvent(
        "testforge:new-terminal",
      ),
    );
  };

  /* ---------------------------------------------------------------------- */
  /* GO                                                                      */
  /* ---------------------------------------------------------------------- */

  const handleShowWelcome = () => {
    setActiveFile(null);
  };

  const handleFocusExplorer = () => {
    setActiveView("explorer");
  };

  const handleFocusAI = () => {
    setShowAI(true);
  };

  /* ---------------------------------------------------------------------- */
  /* HELP                                                                    */
  /* ---------------------------------------------------------------------- */

  const handleAbout = () => {
    window.alert(
      "TestForge IDE\n\n" +
        "Agentic AI-Based Intelligent Software Testing IDE\n\n" +
        "Version 0.1.0",
    );
  };

  /* ---------------------------------------------------------------------- */
  /* LEFT PANEL                                                              */
  /* ---------------------------------------------------------------------- */

  const renderLeftPanel = () => {
    /*
     * No left panel
     */
    if (activeView === null) {
      return null;
    }

    /*
     * Explorer
     */
    if (activeView === "explorer") {
      return (
        <div
          id="testforge-explorer"
          className="min-h-0 w-[260px] min-w-[220px] shrink-0"
        >
          <Explorer
            onFileOpen={(path) => {
              setActiveFile(path);

              console.log(
                "File selected:",
                path,
              );
            }}
          />
        </div>
      );
    }

    /*
     * Search / Git / Run / Analytics
     */
    return (
      <div className="min-h-0 w-[300px] min-w-[260px] shrink-0">
        <ActivityPanel
          view={activeView}
        />
      </div>
    );
  };

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#0d1117] text-[#c9d1d9]">
      {/* ================================================================== */}
      {/* TOP MENU                                                           */}
      {/* ================================================================== */}

      <TopBar
        showExplorer={
          activeView === "explorer"
        }
        showAI={showAI}
        showBottomPanel={
          showBottomPanel
        }
        onToggleExplorer={() =>
          setActiveView(
            activeView === "explorer"
              ? null
              : "explorer",
          )
        }
        onToggleAI={() =>
          setShowAI(
            (current) => !current,
          )
        }
        onToggleBottomPanel={() =>
          setShowBottomPanel(
            (current) => !current,
          )
        }
        onOpenRepository={
          handleOpenRepository
        }
        onSave={handleSave}
        onCloseWorkspace={
          handleCloseWorkspace
        }
        onExit={handleExit}
        onRunTests={handleRunTests}
        onRunCurrentTest={
          handleRunCurrentTest
        }
        onDebugTests={handleDebugTests}
        onClearTerminal={
          handleClearTerminal
        }
        onNewTerminal={
          handleNewTerminal
        }
        onShowWelcome={
          handleShowWelcome
        }
        onFocusExplorer={
          handleFocusExplorer
        }
        onFocusAI={handleFocusAI}
        onAbout={handleAbout}
      />

      {/* ================================================================== */}
      {/* WORKSPACE                                                          */}
      {/* ================================================================== */}

      <div className="flex min-h-0 min-w-0 flex-1">
        {/* ================================================================ */}
        {/* ACTIVITY BAR                                                      */}
        {/* ================================================================ */}

        <ActivityBar
          activeView={activeView}
          aiOpen={showAI}
          onViewChange={
            handleActivityViewChange
          }
          onAIToggle={handleAIToggle}
        />

        {/* ================================================================ */}
        {/* LEFT SIDEBAR                                                      */}
        {/* ================================================================ */}

        {renderLeftPanel()}

        {/* ================================================================ */}
        {/* CENTER EDITOR + BOTTOM PANEL                                     */}
        {/* ================================================================ */}

        <main
          className={`grid min-h-0 min-w-0 flex-1 ${
            showBottomPanel
              ? "grid-rows-[minmax(0,1fr)_210px]"
              : "grid-rows-[minmax(0,1fr)]"
          }`}
        >
          <Editor
            filePath={activeFile}
            onActivePathChange={setActiveFile}
          />

          {showBottomPanel && (
            <BottomPanel />
          )}
        </main>

        {/* ================================================================ */}
        {/* RIGHT AI PANEL                                                    */}
        {/* ================================================================ */}

        {showAI && (
          <aside
            id="testforge-ai-panel"
            className="min-h-0 w-[340px] min-w-[300px] shrink-0 border-l border-[#252a33] bg-[#0d1117]"
          >
            <AIPanel />
          </aside>
        )}
      </div>

      {/* ================================================================== */}
      {/* STATUS BAR                                                         */}
      {/* ================================================================== */}

      <StatusBar />
    </div>
  );
}
