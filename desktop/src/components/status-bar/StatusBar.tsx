import { GitBranch, Radio } from "lucide-react";

export default function StatusBar() {
  return (
    <footer className="flex h-6 shrink-0 items-center justify-between bg-[#161b22] px-3 text-[10px] text-[#c9d1d9]">
      <div className="flex h-full items-center gap-4">
        <span className="flex items-center gap-1">
          <GitBranch size={11} />
          main
        </span>

        <span className="text-emerald-400">
          ✓ 0
        </span>

        <span className="text-red-400">
          × 0
        </span>

        <span className="text-[#8b949e]">
          TestForge
        </span>
      </div>

      <div className="flex h-full items-center gap-4">
        <span>Ln 1, Col 1</span>
        <span>Spaces: 4</span>
        <span>UTF-8</span>
        <span>TypeScript</span>

        <span className="flex items-center gap-1 text-emerald-400">
          <Radio size={10} />
          AI Ready
        </span>
      </div>
    </footer>
  );
}