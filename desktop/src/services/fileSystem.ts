import type { FileSystemEntry } from "../types/electron";

export async function openRepository(): Promise<
  string | null
> {
  return window.electronAPI.openFolder();
}

export async function readDirectory(
  path: string,
): Promise<FileSystemEntry[]> {
  return window.electronAPI.readDirectory(path);
}

export async function readFile(
  path: string,
): Promise<string> {
  return window.electronAPI.readFile(path);
}

export async function saveFile(
  path: string,
  content: string,
): Promise<boolean> {
  return window.electronAPI.saveFile(
    path,
    content,
  );
}