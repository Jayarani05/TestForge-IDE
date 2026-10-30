import { useEffect, useRef, useState } from "react";
import { CircleAlert, CircleCheck, CircleDot, List, Terminal as TerminalIcon, Trash2 } from "lucide-react";
import { useRepositoryStore } from "../stores/repositoryStore";

type PanelTab = "TERMINAL" | "OUTPUT" | "PROBLEMS" | "TEST RESULTS";
interface CommandRecord { command: string; stdout: string; stderr: string; exitCode: number; }

export default function BottomPanel() {
  const { rootPath, isAnalyzing, analysis, error } = useRepositoryStore();
  const [activeTab, setActiveTab] = useState<PanelTab>("TERMINAL");
  const [command, setCommand] = useState("");
  const [running, setRunning] = useState(false);
  const [commands, setCommands] = useState<CommandRecord[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const clear = () => setCommands([]);
    const newTerminal = () => { setActiveTab("TERMINAL"); inputRef.current?.focus(); };
    window.addEventListener("testforge:clear-terminal", clear);
    window.addEventListener("testforge:new-terminal", newTerminal);
    return () => {
      window.removeEventListener("testforge:clear-terminal", clear);
      window.removeEventListener("testforge:new-terminal", newTerminal);
    };
  }, []);

  const runCommand = async () => {
    const value = command.trim();
    if (!value || running) return;
    if (!rootPath) {
      setCommands((current) => [...current, { command: value, stdout: "", stderr: "Open a workspace before running commands.", exitCode: 1 }]);
      setCommand("");
      return;
    }
    setCommand("");
    setRunning(true);
    setActiveTab("TERMINAL");
    try {
      const result = await window.electronAPI.executeCommand(value, rootPath);
      setCommands((current) => [...current, { command: value, ...result }]);
    } catch (cause) {
      setCommands((current) => [...current, { command: value, stdout: "", stderr: cause instanceof Error ? cause.message : "Command failed to start.", exitCode: 1 }]);
    } finally {
      setRunning(false);
    }
  };

  const tabs: { name: PanelTab; icon: typeof TerminalIcon }[] = [
    { name: "PROBLEMS", icon: CircleAlert }, { name: "OUTPUT", icon: List },
    { name: "TERMINAL", icon: TerminalIcon }, { name: "TEST RESULTS", icon: CircleCheck },
  ];

  return (
    <section className="flex min-h-0 flex-col border-t border-[#303030] bg-[#181818]">
      <div className="flex h-9 shrink-0 items-center border-b border-[#303030]">
        {tabs.map(({ name, icon: Icon }) => <button key={name} onClick={() => setActiveTab(name)} className={`flex h-full items-center gap-1.5 border-b-2 px-4 text-[10px] font-semibold tracking-wide ${activeTab === name ? "border-[#3794ff] text-white" : "border-transparent text-[#858585] hover:text-white"}`}><Icon size={12} />{name}</button>)}
        <button title="Clear terminal" onClick={() => setCommands([])} className="ml-auto mr-2 rounded p-1 text-[#858585] hover:bg-[#333] hover:text-white"><Trash2 size={13} /></button>
      </div>

      {activeTab === "TERMINAL" && <>
        <div className="min-h-0 flex-1 overflow-auto px-4 py-2 font-mono text-[11px] leading-5">
          {commands.length === 0 && <div className="text-[#747474]">{rootPath ? `Workspace terminal · ${rootPath}` : "Open a workspace to run commands."}</div>}
          {commands.map((record, index) => <div key={`${index}-${record.command}`} className="mb-2">
            <div><span className="text-[#4ec9b0]">PS</span> <span className="text-[#569cd6]">{rootPath ? rootPath.split(/[\\/]/).pop() : "workspace"}</span> <span className="text-[#d4d4d4]">&gt; {record.command}</span></div>
            {record.stdout && <pre className="whitespace-pre-wrap text-[#d4d4d4]">{record.stdout}</pre>}
            {record.stderr && <pre className="whitespace-pre-wrap text-[#f48771]">{record.stderr}</pre>}
            <div className={record.exitCode === 0 ? "text-[#6a9955]" : "text-[#f48771]"}>Process exited with code {record.exitCode}</div>
          </div>)}
          {running && <div className="text-[#858585]">Command is running…</div>}
        </div>
        <form onSubmit={(event) => { event.preventDefault(); void runCommand(); }} className="flex h-8 shrink-0 items-center gap-2 border-t border-[#292929] px-4 font-mono text-[11px]">
          <span className="text-[#4ec9b0]">›</span><input ref={inputRef} value={command} onChange={(event) => setCommand(event.target.value)} disabled={running} placeholder="Enter a command…" className="min-w-0 flex-1 bg-transparent text-[#d4d4d4] outline-none placeholder:text-[#666]" aria-label="Terminal command" />
          <button disabled={!command.trim() || running} className="text-[10px] text-[#858585] hover:text-white disabled:opacity-40">Run ↵</button>
        </form>
      </>}

      {activeTab === "OUTPUT" && <div className="min-h-0 flex-1 overflow-auto px-4 py-3 font-mono text-[11px] leading-5">
        {isAnalyzing && <div className="text-[#d7ba7d]">Repository analysis and context indexing are running…</div>}
        {analysis && <div className="text-[#89d185]">Repository analysis and context indexing completed.</div>}
        {error && <div className="text-[#f48771]">{error}</div>}
        {!isAnalyzing && !analysis && !error && <div className="text-[#747474]">TestForge and extension output will appear here.</div>}
      </div>}

      {activeTab === "PROBLEMS" && <div className="flex min-h-0 flex-1 items-center justify-center gap-2 text-xs text-[#858585]"><CircleDot size={14} /> No problems reported in the current workspace.</div>}
      {activeTab === "TEST RESULTS" && <div className="flex min-h-0 flex-1 items-center justify-center gap-2 text-xs text-[#858585]"><CircleCheck size={14} /> Run a test command or use TestForge to see results.</div>}
    </section>
  );
}
