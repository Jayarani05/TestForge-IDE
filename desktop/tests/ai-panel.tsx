import { useState } from "react";
import { createRoot } from "react-dom/client";

import AIPanel from "../src/components/ai-panel/AIPanel";
import ActivityPanel from "../src/components/activity-panel/ActivityPanel";
import { repositoryStore } from "../src/components/stores/repositoryStore";
import Editor from "../src/components/editor/Editor";
import { editorStore } from "../src/components/stores/editorStore";

const trackedEvents = [
  "testforge:generate-tests",
  "testforge:analyze-failure",
  "testforge:self-heal",
  "testforge:analytics",
  "testforge:open-ai",
];

const listeners = new Map<
  string,
  Set<EventListenerOrEventListenerObject>
>(
  trackedEvents.map((eventName) => [
    eventName,
    new Set(),
  ]),
);

const addEventListener = window.addEventListener.bind(window);
const removeEventListener = window.removeEventListener.bind(window);

window.addEventListener = ((
  type: string,
  listener: EventListenerOrEventListenerObject,
  options?: boolean | AddEventListenerOptions,
) => {
  listeners.get(type)?.add(listener);
  addEventListener(type, listener, options);
}) as typeof window.addEventListener;

window.removeEventListener = ((
  type: string,
  listener: EventListenerOrEventListenerObject,
  options?: boolean | EventListenerOptions,
) => {
  listeners.get(type)?.delete(listener);
  removeEventListener(type, listener, options);
}) as typeof window.removeEventListener;

declare global {
  interface Window {
    testforgeListenerCount(eventName: string): number;
    testforgeActiveEditorTab(): ReturnType<typeof editorStore.getState>["tabs"][number] | null;
  }
}

window.testforgeListenerCount = (eventName) =>
  listeners.get(eventName)?.size ?? 0;
window.testforgeActiveEditorTab = () => {
  const state = editorStore.getState();
  return state.tabs.find((tab) => tab.id === state.activeTabId) ?? null;
};

repositoryStore.setRepository("/test/repository");

export function Harness() {
  const [visible, setVisible] = useState(true);
  const [activityView, setActivityView] = useState<"run" | "analytics">("run");
  const [, setRevision] = useState(0);

  return (
    <main>
      <button
        type="button"
        onClick={() => setRevision((revision) => revision + 1)}
      >
        Rerender harness
      </button>
      <button
        type="button"
        onClick={() => setVisible(false)}
      >
        Unmount panel
      </button>
      <button
        type="button"
        onClick={() =>
          window.dispatchEvent(
            new CustomEvent("testforge:open-file", {
              detail: {
                path: "/test/repository/tests/test_orders.py",
                name: "test_orders.py",
                content: "def test_order():\n    assert True\n",
              },
            }),
          )
        }
      >
        Open test fixture
      </button>
      <button
        type="button"
        onClick={() =>
          window.dispatchEvent(
            new CustomEvent("testforge:open-file", {
              detail: {
                path: "/test/repository/src/orders.py",
                name: "orders.py",
                content: "def create_order():\n    return {}\n",
              },
            }),
          )
        }
      >
        Open invalid test fixture
      </button>
      <button
        type="button"
        onClick={() =>
          window.dispatchEvent(
            new CustomEvent("testforge:open-file", {
              detail: {
                path: "/test/repository/web/tests/orders.spec.ts",
                name: "orders.spec.ts",
                content: 'import { test } from "@playwright/test";\n',
              },
            }),
          )
        }
      >
        Open browser test fixture
      </button>
      <button type="button" onClick={() => setActivityView("analytics")}>
        Open analytics
      </button>
      <button type="button" onClick={() => setActivityView("run")}>
        Open run panel
      </button>
      <ActivityPanel view={activityView} />
      {visible && (
        <>
          <AIPanel />
          <Editor />
        </>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<Harness />);
