export {};

interface WorkspaceNode {
  name: string;
  path: string;
  isDirectory: boolean;
  children: WorkspaceNode[];
}

interface TerminalResult {
  stdout: string;
  stderr: string;
  exitCode: number;
}

declare global {
  interface Window {
    electronAPI: {
      // Workspace
      openFolder(): Promise<string | null>;

      readDirectory(
        path: string
      ): Promise<WorkspaceNode[]>;

      // File System
      readFile(path: string): Promise<string>;

      saveFile(
        path: string,
        content: string
      ): Promise<boolean>;

      // Terminal
      executeCommand(
        command: string,
        cwd?: string
      ): Promise<TerminalResult>;
    };
  }
}