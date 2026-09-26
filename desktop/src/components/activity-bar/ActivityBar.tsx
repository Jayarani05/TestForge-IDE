export default function ActivityBar() {
  return (
    <aside className="activity-bar">
      <button title="Explorer">📁</button>
      <button title="Search">🔍</button>
      <button title="Testing">🧪</button>
      <button title="Source Control">🌿</button>

      <div className="activity-bottom">
        <button title="Settings">⚙️</button>
      </div>
    </aside>
  );
}