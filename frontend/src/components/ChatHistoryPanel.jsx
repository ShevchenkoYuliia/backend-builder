export default function ChatHistoryPanel({
  history,
  activeChatId,
  loading,
  onOpen,
  onNew,
}) {
  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Chat History</span>
          <h3>Історія AI-запитів</h3>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <div className="chip">{history.length}</div>
          <button
            id="new-chat-btn"
            className="ghost-button"
            style={{
              padding: "0.3rem 0.7rem",
              fontSize: "0.78rem",
              borderRadius: "8px",
              whiteSpace: "nowrap",
            }}
            onClick={onNew}
            title="Почати новий AI-запит"
          >
            + Новий
          </button>
        </div>
      </div>

      <div className="project-list">
        {history.map((item) => (
          <button
            key={item.id}
            className={`history-card ${activeChatId === item.id ? "history-card-active" : ""}`}
            onClick={() => onOpen(item.id)}
            style={{
              border: item.status === "помилка" ? "1px solid #f87171" : undefined,
              background: item.status === "помилка" ? "rgba(248, 113, 113, 0.08)" : undefined,
            }}
          >
            <strong>{item.prompt}</strong>
            <span>{item.model}</span>
            {item.failed_attempts > 0 && (
              <span style={{ color: "#f87171", fontSize: "0.75rem", marginTop: "0.4rem" }}>
                Невд.: {item.failed_attempts}
              </span>
            )}
          </button>
        ))}

        {history.length === 0 && !loading ? (
          <div className="empty-inline">
            Поки немає історії. Спочатку відправте ідею в AI.
          </div>
        ) : null}
      </div>
    </section>
  );
}
