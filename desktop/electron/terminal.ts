import { spawn } from "node:child_process";

export interface TerminalResult {
  stdout: string;
  stderr: string;
  exitCode: number;
}

export function executeCommand(
  command: string,
  cwd?: string
): Promise<TerminalResult> {
  return new Promise((resolve) => {
    const shell =
      process.platform === "win32"
        ? "cmd.exe"
        : "bash";

    const args =
      process.platform === "win32"
        ? ["/c", command]
        : ["-c", command];

    const child = spawn(shell, args, {
      cwd,
      windowsHide: true,
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    child.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    child.on("close", (code) => {
      resolve({
        stdout,
        stderr,
        exitCode: code ?? 0,
      });
    });
  });
}