import { contextBridge, ipcRenderer } from "electron";

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

    createFile: (path: string) =>
      ipcRenderer.invoke("fs:createFile", path),

    createDirectory: (path: string) =>
      ipcRenderer.invoke("fs:createDirectory", path),

    renamePath: (oldPath: string, newPath: string) =>
      ipcRenderer.invoke("fs:rename", oldPath, newPath),

    deletePath: (path: string) =>
      ipcRenderer.invoke("fs:delete", path),

    ensureOutputs: (workspacePath: string) =>
      ipcRenderer.invoke("fs:ensureOutputs", workspacePath),

    executeCommand: (
      command: string,
      cwd?: string
    ) =>
      ipcRenderer.invoke(
        "terminal:execute",
        command,
        cwd
      ),

    startTerminal: (cwd: string) =>
      ipcRenderer.invoke("terminal:start", cwd),

    writeTerminal: (input: string) =>
      ipcRenderer.invoke("terminal:write", input),

    stopTerminal: () =>
      ipcRenderer.invoke("terminal:stop"),

    onTerminalOutput: (listener: (output: string) => void) => {
      const handler = (_event: Electron.IpcRendererEvent, output: string) => listener(output);
      ipcRenderer.on("terminal:output", handler);
      return () => ipcRenderer.removeListener("terminal:output", handler);
    },

    onTerminalExit: (listener: () => void) => {
      const handler = () => listener();
      ipcRenderer.on("terminal:exit", handler);
      return () => ipcRenderer.removeListener("terminal:exit", handler);
    },
  }
);

