import MainLayout from "./layouts/MainLayout";

import ActivityBar from "./components/activity-bar/ActivityBar";
import Explorer from "./components/explorer/Explorer";
import Editor from "./components/editor/Editor";
import AIPanel from "./components/ai-panel/AIPanel";
import StatusBar from "./components/status-bar/StatusBar";

import "./App.css";

function App() {
  return (
    <MainLayout
      activityBar={<ActivityBar />}
      explorer={<Explorer />}
      editor={<Editor />}
      aiPanel={<AIPanel />}
      statusBar={<StatusBar />}
    />
  );
}

export default App;