import {
  BarChart3,
  Bot,
  Files,
  GitBranch,
  Blocks,
  Play,
  Search,
} from "lucide-react";

export type ActivityView =
  | "explorer"
  | "search"
  | "source-control"
  | "run"
  | "analytics"
  | "extensions"
  | null;

interface ActivityBarProps {
  activeView: ActivityView;
  aiOpen: boolean;

  onViewChange: (
    view: ActivityView,
  ) => void;

  onAIToggle: () => void;
}

interface ActivityItem {
  id: Exclude<ActivityView, null>;
  label: string;
  icon: typeof Files;
}

const activityItems: ActivityItem[] = [
  {
    id: "explorer",
    label: "Explorer",
    icon: Files,
  },
  {
    id: "search",
    label: "Search",
    icon: Search,
  },
  {
    id: "source-control",
    label: "Source Control",
    icon: GitBranch,
  },
  {
    id: "run",
    label: "Run and Test",
    icon: Play,
  },
  {
    id: "analytics",
    label: "Test Analytics",
    icon: BarChart3,
  },
  {
    id: "extensions",
    label: "Extensions",
    icon: Blocks,
  },
];

export default function ActivityBar({
  activeView,
  aiOpen,
  onViewChange,
  onAIToggle,
}: ActivityBarProps) {
  const handleViewClick = (
    view: Exclude<ActivityView, null>,
  ) => {
    if (activeView === view) {
      onViewChange(null);
      return;
    }

    onViewChange(view);
  };

  return (
    <aside className="relative z-40 flex h-full w-[52px] shrink-0 flex-col border-r border-[#252a33] bg-[#0b0f14]">
      <div className="flex flex-1 flex-col items-center">
        {activityItems.slice(0, 2).map(
          (item) => {
            const Icon = item.icon;
            const isActive =
              activeView === item.id;

            return (
              <button
                key={item.id}
                type="button"
                title={item.label}
                aria-label={item.label}
                aria-pressed={isActive}
                onClick={() =>
                  handleViewClick(
                    item.id,
                  )
                }
                className={`relative flex h-[52px] w-[52px] shrink-0 items-center justify-center transition-colors ${
                  isActive
                    ? "bg-[#161b22] text-white"
                    : "text-[#8b949e] hover:bg-[#161b22] hover:text-[#d7dae0]"
                }`}
              >
                {isActive && (
                  <span className="absolute left-0 top-0 h-full w-[2px] bg-[#3794ff]" />
                )}

                <Icon
                  size={23}
                  strokeWidth={
                    isActive ? 1.8 : 1.5
                  }
                />
              </button>
            );
          },
        )}

        {/* AI */}
        <button
          type="button"
          title="TestForge AI"
          aria-label="TestForge AI"
          aria-pressed={aiOpen}
          onClick={onAIToggle}
          className={`relative flex h-[52px] w-[52px] shrink-0 items-center justify-center transition-colors ${
            aiOpen
              ? "bg-[#161b22] text-white"
              : "text-[#8b949e] hover:bg-[#161b22] hover:text-[#d7dae0]"
          }`}
        >
          {aiOpen && (
            <span className="absolute left-0 top-0 h-full w-[2px] bg-[#3794ff]" />
          )}

          <Bot
            size={23}
            strokeWidth={
              aiOpen ? 1.8 : 1.5
            }
          />
        </button>

        {activityItems.slice(2).map(
          (item) => {
            const Icon = item.icon;
            const isActive =
              activeView === item.id;

            return (
              <button
                key={item.id}
                type="button"
                title={item.label}
                aria-label={item.label}
                aria-pressed={isActive}
                onClick={() =>
                  handleViewClick(
                    item.id,
                  )
                }
                className={`relative flex h-[52px] w-[52px] shrink-0 items-center justify-center transition-colors ${
                  isActive
                    ? "bg-[#161b22] text-white"
                    : "text-[#8b949e] hover:bg-[#161b22] hover:text-[#d7dae0]"
                }`}
              >
                {isActive && (
                  <span className="absolute left-0 top-0 h-full w-[2px] bg-[#3794ff]" />
                )}

                <Icon
                  size={23}
                  strokeWidth={
                    isActive ? 1.8 : 1.5
                  }
                />
              </button>
            );
          },
        )}
      </div>

      <div className="flex h-8 w-full shrink-0 items-center justify-center border-t border-[#1d222a]">
        <span className="text-[9px] font-semibold text-[#484f58]">
          TF
        </span>
      </div>
    </aside>
  );
}
