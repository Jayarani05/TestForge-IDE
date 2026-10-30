import { app, BrowserWindow, ipcMain, dialog } from "electron";
import path from "node:path";
import fs from "node:fs/promises";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";

import { executeCommand } from "./terminal";

const __dirname = path.join(app.getAppPath(), "dist-electron");

let win: BrowserWindow | null = null;
let terminalProcess: ChildProcessWithoutNullStreams | null = null;

const IGNORED_DIRECTORIES = new Set([
  ".git",
  ".hg",
  ".svn",
  "node_modules",
  ".venv",
  "venv",
  "__pycache__",
  ".pytest_cache",
  ".mypy_cache",
  ".ruff_cache",
  ".tox",
  ".idea",
  ".vscode",
  ".cache",
  ".parcel-cache",
  ".turbo",
  ".vite",
  "dist",
  "dist-electron",
  "build",
  "coverage",
  ".next",
  ".nuxt",
  "target",
  "out",
  "bin",
  "obj",
]);

function stopTerminal() {
  if (!terminalProcess) return;
  terminalProcess.kill();
  terminalProcess = null;
}

function createWindow() {
  win = new BrowserWindow({
    width: 1600,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    show: true,

    webPreferences: {
      preload: path.join(
        __dirname,
        "preload.js"
      ),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const devServerUrl =
    process.env.VITE_DEV_SERVER_URL;

  if (devServerUrl) {
    win.loadURL(devServerUrl);
  } else {
    win.loadFile(
      path.join(
        __dirname,
        "../dist/index.html"
      )
    );
  }
}

async function buildTree(
  folder: string,
): Promise<
  {
    name: string;
    path: string;
    type: "file" | "directory";
  }[]
> {
  const entries = await fs.readdir(
    folder,
    { withFileTypes: true },
  );

  const nodes = entries
    .filter(
      (entry) =>
        !entry.isSymbolicLink() &&
        !(
          entry.isDirectory() &&
          IGNORED_DIRECTORIES.has(entry.name)
        ),
    )
    .map((entry) => ({
      name: entry.name,
      path: path.join(folder, entry.name),
      type: entry.isDirectory()
        ? "directory" as const
        : "file" as const,
    }));

  return nodes.sort((a, b) => {
    if (
      a.type === "directory" &&
      b.type !== "directory"
    ) {
      return -1;
    }

    if (
      a.type !== "directory" &&
      b.type === "directory"
    ) {
      return 1;
    }

    return a.name.localeCompare(b.name);
  });
}

ipcMain.handle(
  "dialog:openFolder",
  async () => {
    const result =
      await dialog.showOpenDialog({
        properties: [
          "openDirectory",
        ],
      });

    if (result.canceled) {
      return null;
    }

    return result.filePaths[0];
  }
);

ipcMain.handle(
  "fs:readDirectory",
  async (_, folderPath: string) => {
    return buildTree(folderPath);
  }
);

ipcMain.handle(
  "fs:readFile",
  async (_, filePath: string) => {
    return fs.readFile(
      filePath,
      "utf-8"
    );
  }
);

ipcMain.handle(
  "fs:saveFile",
  async (
    _,
    filePath: string,
    content: string
  ) => {
    await fs.writeFile(
      filePath,
      content,
      "utf-8"
    );

    return true;
  }
);

ipcMain.handle("fs:createFile", async (_, filePath: string) => {
  await fs.writeFile(filePath, "", { flag: "wx" });
  return true;
});

ipcMain.handle("fs:createDirectory", async (_, folderPath: string) => {
  await fs.mkdir(folderPath);
  return true;
});

ipcMain.handle("fs:rename", async (_, oldPath: string, newPath: string) => {
  await fs.rename(oldPath, newPath);
  return true;
});

ipcMain.handle("fs:delete", async (_, targetPath: string) => {
  await fs.rm(targetPath, { recursive: true, force: false });
  return true;
});

ipcMain.handle("fs:ensureOutputs", async (_, workspacePath: string) => {
  const outputsPath = path.join(workspacePath, "outputs");
  await fs.mkdir(outputsPath, { recursive: true });
  await Promise.all(
    ["tests", "automation", "execution", "reports", "repairs", "screenshots", "exports"].map(
      (folder) => fs.mkdir(path.join(outputsPath, folder), { recursive: true }),
    ),
  );
  return outputsPath;
});

ipcMain.handle(
  "terminal:execute",
  async (
    _,
    command: string,
    cwd?: string
  ) => {
    return executeCommand(
      command,
      cwd
    );
  }
);

ipcMain.handle("terminal:start", async (_, cwd: string) => {
  const workspace = await fs.stat(cwd);
  if (!workspace.isDirectory()) throw new Error("Terminal workspace must be a directory.");
  stopTerminal();

  const shell = process.platform === "win32"
    ? spawn("powershell.exe", ["-NoLogo", "-NoProfile", "-NoExit"], { cwd, windowsHide: true })
    : spawn("bash", ["--noprofile", "--norc", "-i"], { cwd });
  terminalProcess = shell;

  shell.stdout.on("data", (chunk: Buffer) => {
    win?.webContents.send("terminal:output", chunk.toString());
  });
  shell.stderr.on("data", (chunk: Buffer) => {
    win?.webContents.send("terminal:output", chunk.toString());
  });
  shell.on("error", (error) => {
    win?.webContents.send("terminal:output", `\r\n${error.message}\r\n`);
  });
  shell.on("close", (code) => {
    if (terminalProcess === shell) terminalProcess = null;
    win?.webContents.send("terminal:output", `\r\n[Shell exited with code ${code ?? 0}]\r\n`);
    win?.webContents.send("terminal:exit");
  });
  return true;
});

ipcMain.handle("terminal:write", async (_, input: string) => {
  if (!terminalProcess || terminalProcess.killed || !terminalProcess.stdin.writable) {
    throw new Error("The terminal shell is not running.");
  }
  terminalProcess.stdin.write(input);
});

ipcMain.handle("terminal:stop", () => stopTerminal());

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (
      BrowserWindow
        .getAllWindows()
        .length === 0
    ) {
      createWindow();
    }
  });
});

app.on(
  "window-all-closed",
  () => {
    stopTerminal();
    if (
      process.platform !== "darwin"
    ) {
      app.quit();
    }
  }
);
