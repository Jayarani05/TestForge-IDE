import {
  app,
  BrowserWindow,
  ipcMain,
  dialog,
} from "electron";

import path from "node:path";
import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { executeCommand } from "./terminal";

const __dirname = path.dirname(
  fileURLToPath(import.meta.url)
);

let win: BrowserWindow | null = null;

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
        "preload.mjs"
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
  folder: string
): Promise<any[]> {
  const entries = await fs.readdir(
    folder,
    { withFileTypes: true }
  );

  const nodes = await Promise.all(
    entries.map(async (entry) => {
      const fullPath = path.join(
        folder,
        entry.name
      );

      return {
        name: entry.name,
        path: fullPath,
        isDirectory:
          entry.isDirectory(),

        children: entry.isDirectory()
          ? await buildTree(fullPath)
          : [],
      };
    })
  );

  return nodes.sort((a, b) => {
    if (
      a.isDirectory &&
      !b.isDirectory
    ) {
      return -1;
    }

    if (
      !a.isDirectory &&
      b.isDirectory
    ) {
      return 1;
    }

    return a.name.localeCompare(
      b.name
    );
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
    if (
      process.platform !== "darwin"
    ) {
      app.quit();
    }
  }
);