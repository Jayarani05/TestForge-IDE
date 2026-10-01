import { useSyncExternalStore } from "react";

export interface EditorTab {
  id: string;
  path: string;
  name: string;
  language: string;
  content: string;
  savedContent: string;
  isDirty: boolean;
}

interface EditorState {
  tabs: EditorTab[];
  activeTabId: string | null;
}

const initialState: EditorState = {
  tabs: [],
  activeTabId: null,
};

let state: EditorState = initialState;

const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => {
    listener();
  });
}

function createTabId(path: string) {
  return path.toLowerCase();
}

export const editorStore = {
  getState() {
    return state;
  },

  subscribe(listener: () => void) {
    listeners.add(listener);

    return () => {
      listeners.delete(listener);
    };
  },

  openFile(tab: EditorTab) {
    const id = createTabId(tab.path);

    const existing = state.tabs.find(
      (item) => item.id === id,
    );

    if (existing) {
      state = {
        ...state,
        activeTabId: id,
      };

      emit();
      return;
    }

    state = {
      ...state,
      tabs: [
        ...state.tabs,
        {
          ...tab,
          id,
        },
      ],
      activeTabId: id,
    };

    emit();
  },

  updateContent(
    tabId: string,
    content: string,
  ) {
    state = {
      ...state,
      tabs: state.tabs.map((tab) =>
        tab.id === tabId
          ? {
              ...tab,
              content,
              isDirty:
                content !==
                tab.savedContent,
            }
          : tab,
      ),
    };

    emit();
  },

  markSaved(
    tabId: string,
    content: string,
  ) {
    state = {
      ...state,
      tabs: state.tabs.map((tab) =>
        tab.id === tabId
          ? {
              ...tab,
              content,
              savedContent:
                content,
              isDirty: false,
            }
          : tab,
      ),
    };

    emit();
  },

  activateTab(tabId: string) {
    const exists = state.tabs.some(
      (tab) => tab.id === tabId,
    );

    if (!exists) {
      return;
    }

    state = {
      ...state,
      activeTabId: tabId,
    };

    emit();
  },

  closeTab(tabId: string) {
    const index =
      state.tabs.findIndex(
        (tab) => tab.id === tabId,
      );

    if (index === -1) {
      return;
    }

    const remaining =
      state.tabs.filter(
        (tab) => tab.id !== tabId,
      );

    let activeTabId =
      state.activeTabId;

    if (
      activeTabId === tabId
    ) {
      const nextTab =
        remaining[index] ??
        remaining[index - 1] ??
        remaining[0] ??
        null;

      activeTabId =
        nextTab?.id ?? null;
    }

    state = {
      tabs: remaining,
      activeTabId,
    };

    emit();
  },

  closeAll() {
    state = {
      tabs: [],
      activeTabId: null,
    };

    emit();
  },
};

export function useEditorStore() {
  return useSyncExternalStore(
    editorStore.subscribe,
    editorStore.getState,
  );
}