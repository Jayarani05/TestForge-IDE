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
      openFolder(): Promise<string | null>;

      readDirectory(
        path: string
      ): Promise<WorkspaceNode[]>;

      readFile(path: string): Promise<string>;

      saveFile(
        path: string,
        content: string
      ): Promise<boolean>;

      executeCommand(
        command: string,
        cwd?: string
      ): Promise<TerminalResult>;
    };
  }
}