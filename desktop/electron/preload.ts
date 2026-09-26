import {
  contextBridge,
  ipcRenderer,
} from "electron";

contextBridge.exposeInMainWorld(
  "electronAPI",
  {
    openFolder: () =>
      ipcRenderer.invoke(
        "dialog:openFolder"
      ),

    readDirectory: (path: string) =>
      ipcRenderer.invoke(
        "fs:readDirectory",
        path
      ),

    readFile: (path: string) =>
      ipcRenderer.invoke(
        "fs:readFile",
        path
      ),

    saveFile: (
      path: string,
      content: string
    ) =>
      ipcRenderer.invoke(
        "fs:saveFile",
        path,
        content
      ),

    executeCommand: (
      command: string,
      cwd?: string
    ) =>
      ipcRenderer.invoke(
        "terminal:execute",
        command,
        cwd
      ),
  }
);