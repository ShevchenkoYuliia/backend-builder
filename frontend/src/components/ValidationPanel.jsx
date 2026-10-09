const severityLabel = {
  error: "Помилка",
  warning: "Попередження",
};

export default function ValidationPanel({ report, loading, onIssueClick }) {
  const issues = report?.issues ?? [];
  const errorCount = issues.filter((issue) => issue.severity === "error").length;
  const warningCount = issues.filter((issue) => issue.severity === "warning").length;

  return (
    <section className="panel validation-panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Smart Validation</span>
          <h3>Архітектурна перевірка</h3>
        </div>
        <div className={`chip ${report?.valid ? "chip-success" : "chip-danger"}`}>
          {loading ? "перевірка..." : report?.valid ? "готово" : "є помилки"}
        </div>
      </div>

      <div className="stats-row">
        <div className="mini-stat">
          <strong>{errorCount}</strong>
          <span>помилок</span>
        </div>
        <div className="mini-stat">
          <strong>{warningCount}</strong>
          <span>попереджень</span>
        </div>
      </div>

      <div className="issue-list">
        {issues.length === 0 ? (
          <div className="empty-inline">
            Валідатор не знайшов проблем. Можна зберігати проєкт або генерувати ZIP.
          </div>
        ) : null}

        {issues.map((issue, index) => {
          const isClickable = !!(onIssueClick && issue.location?.length);
          return (
            <article
              key={`${issue.code}-${index}`}
              className={`issue-card issue-${issue.severity}`}
              onClick={isClickable ? () => onIssueClick(issue) : undefined}
              style={isClickable ? { cursor: "pointer" } : undefined}
              title={isClickable ? "Натисніть, щоб перейти до поля з проблемою" : undefined}
            >
              <div className="issue-topline">
                <strong>{severityLabel[issue.severity]}</strong>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span>{issue.code}</span>
                  {isClickable && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onIssueClick && onIssueClick(issue);
                      }}
                      className="ghost-button"
                      style={{
                        fontSize: "0.72rem",
                        color: "#14b8a6",
                        background: "rgba(20,184,166,0.12)",
                        borderRadius: "4px",
                        padding: "1px 6px",
                        fontWeight: 600,
                        letterSpacing: "0.02em",
                        cursor: "pointer",
                        border: "none",
                      }}
                    >
                      →
                    </button>
                  )}
                </div>
              </div>
              <p>{issue.message}</p>
              {issue.location?.length ? (
                <small>{issue.location.join(" → ")}</small>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}
