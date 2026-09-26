export default function Explorer() {
  return (
    <aside className="explorer">
      <div className="explorer-header">
        <span>EXPLORER</span>

        <button title="Open Folder">
          📂
        </button>
      </div>

      <div className="empty-explorer">
        <div className="empty-icon">📁</div>

        <h3>No Folder Open</h3>

        <p>
          Open a repository to start
          working with TestForge.
        </p>
      </div>
    </aside>
  );
}