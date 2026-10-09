import { useEffect, useState } from "react";

const STATS_KEY = "builder-stats";

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("uk-UA", {
      day: "2-digit",
      month: "2-digit",
      year: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function exportCsv(records) {
  const cols = [
    "Дата",
    "Запит",
    "Модель",
    "БД",
    "Сутностей",
    "Полів",
    "Зв'язків",
    "Час LLM (сек)",
    "Загальний час (сек)",
    "Токени",
    "Невдалих спроб",
    "Статус компіляції",
    "Час генерації ZIP (сек)",
    "Час ендпоінтів (сек)",
    "Токени ендпоінтів",
  ];
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const rows = records.map((r) => [
    esc(formatDate(r.timestamp)),
    esc(r.prompt ?? ""),
    esc(r.model ?? ""),
    esc(r.dbType ?? ""),
    esc(r.entitiesCount ?? ""),
    esc(r.fieldsCount ?? ""),
    esc(r.relationsCount ?? ""),
    esc(r.llmTime ?? ""),
    esc(r.totalTime ?? ""),
    esc((r.tokensUsed ?? 0) + (r.endpointsTokens ?? 0)),
    esc(r.failedAttempts ?? 0),
    esc(
      r.compileSuccess === true
        ? "Успішно"
        : r.compileSuccess === false
        ? "Помилка"
        : "—"
    ),
    esc(r.generationTime ?? ""),
    esc(r.endpointsTime ?? ""),
    esc(r.endpointsTokens ?? ""),
  ]);
  const csvContent = [cols.map(esc).join(","), ...rows.map((r) => r.join(","))].join("\n");
  const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `builder-stats-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function StatsPanel({ lastMetrics, validationReport }) {
  const [records, setRecords] = useState([]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STATS_KEY);
      setRecords(raw ? JSON.parse(raw) : []);
    } catch {
      setRecords([]);
    }
  }, [lastMetrics]);

  const handleClear = () => {
    window.localStorage.removeItem(STATS_KEY);
    setRecords([]);
  };

  const avgLlm =
    records.length > 0 && records.some((r) => r.llmTime)
      ? (
          records.filter((r) => r.llmTime).reduce((s, r) => s + parseFloat(r.llmTime || 0), 0) /
          records.filter((r) => r.llmTime).length
        ).toFixed(1)
      : null;

  const totalTokens = records.reduce((s, r) => s + (r.tokensUsed || 0) + (r.endpointsTokens || 0), 0);
  const totalFailed = records.reduce((s, r) => s + (r.failedAttempts || 0), 0);

  // Aggregate counts from all records
  const totalErrors = validationReport?.issues?.filter((i) => i.severity === "error").length ?? 0;
  const totalWarnings = validationReport?.issues?.filter((i) => i.severity === "warning").length ?? 0;

  // Latest stats from lastMetrics
  const latest = records[0] ?? null;

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Analytics</span>
          <h3>Загальна статистика LLM</h3>
        </div>
        <div className="chip">{records.length}</div>
      </div>

      {/* Summary aggregates */}
      {records.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))",
            gap: "0.6rem",
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            background: "#0f1210",
            borderRadius: "8px",
            border: "1px solid #14b8a6",
            fontSize: "0.82rem",
            color: "#94a3b8",
          }}
        >
          <div>
            Запитів: <strong style={{ color: "#e2e8f0" }}>{records.length}</strong>
          </div>
          {avgLlm && (
            <div>
              Сер. час LLM: <strong style={{ color: "#e2e8f0" }}>{avgLlm} сек</strong>
            </div>
          )}
          <div>
            Токени: <strong style={{ color: "#e2e8f0" }}>{totalTokens.toLocaleString()}</strong>
          </div>
          <div>
            Невдалих спроб:{" "}
            <strong style={{ color: totalFailed > 0 ? "#f87171" : "#e2e8f0" }}>{totalFailed}</strong>
          </div>
          <div>
            Помилок: <strong style={{ color: totalErrors > 0 ? "#f87171" : "#e2e8f0" }}>{totalErrors}</strong>
          </div>
          <div>
            Попереджень:{" "}
            <strong style={{ color: totalWarnings > 0 ? "#fbbf24" : "#e2e8f0" }}>{totalWarnings}</strong>
          </div>
        </div>
      )}

      {/* Latest generation quick-view */}
      {latest && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            background: "#0a1512",
            borderRadius: "8px",
            border: "1px solid #1e2923",
            fontSize: "0.82rem",
          }}
        >
          <div style={{ fontWeight: 700, color: "#14b8a6", marginBottom: "0.5rem", fontSize: "0.78rem", letterSpacing: "0.06em", textTransform: "uppercase" }}>
            Останній запит
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.35rem 1.2rem", color: "#94a3b8" }}>
            {latest.dbType && (
              <div>
                БД: <strong style={{ color: "#e2e8f0" }}>{latest.dbType}</strong>
              </div>
            )}
            {latest.entitiesCount != null && (
              <div>
                Сутностей: <strong style={{ color: "#e2e8f0" }}>{latest.entitiesCount}</strong>
              </div>
            )}
            {latest.fieldsCount != null && (
              <div>
                Полів: <strong style={{ color: "#e2e8f0" }}>{latest.fieldsCount}</strong>
              </div>
            )}
            {latest.relationsCount != null && (
              <div>
                Зв'язків: <strong style={{ color: "#e2e8f0" }}>{latest.relationsCount}</strong>
              </div>
            )}
            {latest.llmTime && (
              <div>
                Час генерації: <strong style={{ color: "#a3e635" }}>{latest.llmTime} сек</strong>
              </div>
            )}
            {latest.endpointsTime && (
              <div>
                Час ендпоінтів: <strong style={{ color: "#a3e635" }}>{latest.endpointsTime} сек</strong>
              </div>
            )}
            {latest.draftTime && (
              <div>
                Загальний час: <strong style={{ color: "#e2e8f0" }}>{latest.totalTime ?? latest.draftTime} сек</strong>
              </div>
            )}
            {latest.generationTime && (
              <div>
                Час ZIP: <strong style={{ color: "#e2e8f0" }}>{latest.generationTime} сек</strong>
              </div>
            )}
            {latest.compileSuccess != null && (
              <div>
                Компіляція:{" "}
                <strong style={{ color: latest.compileSuccess ? "#4ade80" : "#f87171" }}>
                  {latest.compileSuccess ? "Успішно" : "Помилка"}
                </strong>
              </div>
            )}
            {latest.failedAttempts != null && latest.failedAttempts > 0 && (
              <div>
                Невдалих спроб: <strong style={{ color: "#f87171" }}>{latest.failedAttempts}</strong>
              </div>
            )}
            {(latest.tokensUsed != null || latest.endpointsTokens != null) && (
              <div>
                Токени: <strong style={{ color: "#e2e8f0" }}>{(latest.tokensUsed ?? 0) + (latest.endpointsTokens ?? 0)}</strong>
              </div>
            )}
            {/* Current validation */}
            {(totalErrors > 0 || totalWarnings > 0) && (
              <div style={{ gridColumn: "span 2", marginTop: "0.2rem", borderTop: "1px solid #1e2923", paddingTop: "0.3rem" }}>
                Поточна валідація:{" "}
                {totalErrors > 0 && (
                  <strong style={{ color: "#f87171" }}>{totalErrors} помил.</strong>
                )}
                {totalErrors > 0 && totalWarnings > 0 && ", "}
                {totalWarnings > 0 && (
                  <strong style={{ color: "#fbbf24" }}>{totalWarnings} попер.</strong>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="project-list" style={{ maxHeight: "320px", overflowY: "auto" }}>
        {records.length === 0 ? (
          <div className="empty-inline">
            Ще немає збережених запитів. Після генерації чернетки дані з'являться тут.
          </div>
        ) : (
          records.map((rec, idx) => (
            <div
              key={`stat-${idx}-${rec.timestamp}`}
              style={{
                padding: "0.6rem 0.85rem",
                marginBottom: "0.4rem",
                background: "#0f1210",
                borderRadius: "8px",
                border: "1px solid #1e2923",
                fontSize: "0.8rem",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "0.25rem",
                  color: "#94a3b8",
                }}
              >
                <span style={{ fontWeight: 600, color: "#cbd5e1" }}>
                  {rec.prompt
                    ? rec.prompt.length > 48
                      ? rec.prompt.slice(0, 48) + "…"
                      : rec.prompt
                    : "Запит"}
                </span>
                <span style={{ whiteSpace: "nowrap", marginLeft: "0.5rem" }}>{formatDate(rec.timestamp)}</span>
              </div>
              <div style={{ display: "flex", gap: "0.8rem", flexWrap: "wrap", color: "#64748b" }}>
                {rec.dbType && <span>БД: <strong style={{ color: "#94a3b8" }}>{rec.dbType}</strong></span>}
                {rec.entitiesCount != null && <span>Сут.: <strong style={{ color: "#94a3b8" }}>{rec.entitiesCount}</strong></span>}
                {rec.fieldsCount != null && <span>Полів: <strong style={{ color: "#94a3b8" }}>{rec.fieldsCount}</strong></span>}
                {rec.relationsCount != null && <span>Зв.: <strong style={{ color: "#94a3b8" }}>{rec.relationsCount}</strong></span>}
                {rec.llmTime && <span>LLM: <strong style={{ color: "#a3e635" }}>{rec.llmTime}с</strong></span>}
                {rec.totalTime && <span>Заг.: <strong style={{ color: "#e2e8f0" }}>{rec.totalTime}с</strong></span>}
                {(rec.tokensUsed != null || rec.endpointsTokens != null) && <span>Токени: <strong style={{ color: "#e2e8f0" }}>{(rec.tokensUsed ?? 0) + (rec.endpointsTokens ?? 0)}</strong></span>}
                {rec.failedAttempts > 0 && (
                  <span>Невд.: <strong style={{ color: "#f87171" }}>{rec.failedAttempts}</strong></span>
                )}
                {rec.compileSuccess === true && <span style={{ color: "#4ade80" }}>✓ Компіл.</span>}
                {rec.compileSuccess === false && <span style={{ color: "#f87171" }}>✗ Компіл.</span>}
                {rec.model && <span style={{ color: "#e2e8f0" }}>{rec.model}</span>}
              </div>
            </div>
          ))
        )}
      </div>

      {records.length > 0 && (
        <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <button
            className="accent-button"
            style={{ fontSize: "0.8rem", padding: "0.4rem 0.9rem" }}
            onClick={() => exportCsv(records)}
          >
            Експорт CSV
          </button>
          <button className="ghost-button" style={{ fontSize: "0.8rem" }} onClick={handleClear}>
            Очистити статистику
          </button>
        </div>
      )}
    </section>
  );
}
