import type { ReactNode } from "react";

interface MainLayoutProps {
  activityBar: ReactNode;
  explorer: ReactNode;
  editor: ReactNode;
  aiPanel: ReactNode;
  statusBar: ReactNode;
}

export default function MainLayout({
  activityBar,
  explorer,
  editor,
  aiPanel,
  statusBar,
}: MainLayoutProps) {
  return (
    <div className="ide">
      {activityBar}
      {explorer}
      {editor}
      {aiPanel}
      {statusBar}
    </div>
  );
}