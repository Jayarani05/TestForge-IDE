export interface FileSystemEntry {
  name: string;
  path: string;
  type: "file" | "directory";
}

export interface ElectronAPI {
  openFolder: () => Promise<string | null>;

  readDirectory: (
    path: string,
  ) => Promise<FileSystemEntry[]>;

  readFile: (
    path: string,
  ) => Promise<string>;

  saveFile: (
    path: string,
    content: string,
  ) => Promise<boolean>;

  createFile: (path: string) => Promise<boolean>;
  createDirectory: (path: string) => Promise<boolean>;
  renamePath: (oldPath: string, newPath: string) => Promise<boolean>;
  deletePath: (path: string) => Promise<boolean>;
  ensureOutputs: (workspacePath: string) => Promise<string>;

  executeCommand: (
    command: string,
    cwd?: string,
  ) => Promise<{
    stdout: string;
    stderr: string;
    exitCode: number;
  }>;

  startTerminal: (cwd: string) => Promise<boolean>;
  writeTerminal: (input: string) => Promise<void>;
  stopTerminal: () => Promise<void>;
  onTerminalOutput: (listener: (output: string) => void) => () => void;
  onTerminalExit: (listener: () => void) => () => void;
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}
