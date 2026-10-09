import { useEffect, useState } from "react";

export default function IdeaPanel({
  prompt,
  loading,
  hasKey,
  activeModel,
  onChange,
  onGenerate,
  assistantMessage,
  progressMessages,
  metrics,
}) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    let interval = null;
    if (loading) {
      interval = setInterval(() => {
        setSeconds((s) => s + 1);
      }, 1000);
    } else {
      setSeconds(0);
    }
    return () => clearInterval(interval);
  }, [loading]);

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">Prompt to Builder</span>
          <h3>Опишіть потрібний бекенд</h3>
        </div>
        <div className="chip">{activeModel || "no model"}</div>
      </div>

      {!hasKey ? (
        <div className="status-banner status-error">
          Спочатку додайте AI API ключ у налаштуваннях — без нього генерація з підказки не працюватиме.
        </div>
      ) : null}

      <label className="field-group">
        <span>Ідея продукту</span>
        <textarea
          rows={5}
          value={prompt}
          onChange={(event) => onChange(event.target.value)}
          placeholder='Наприклад: "Хочу бекенд для інтернет-магазину з користувачами, товарами, кошиком, замовленнями та оплатами."'
        />
      </label>

      <div className="toggle-row">
        <button
          className="accent-button"
          disabled={loading || !hasKey}
          onClick={onGenerate}
        >
          {loading ? `AI працює... (${seconds}с)` : "Згенерувати структуру"}
        </button>
      </div>

      {loading && (
        <div className="status-banner status-info" style={{ marginTop: "1rem" }}>
          Запит обробляється. Це може зайняти деякий час.
        </div>
      )}

      {progressMessages?.length > 0 && (
        <div
          style={{
            marginTop: "1rem",
            padding: "0.9rem 1rem",
            border: "1px solid #1e2923",
            borderRadius: "12px",
            background: "#0a1512",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: "0.6rem", color: "#14b8a6", fontSize: "0.78rem", letterSpacing: "0.06em", textTransform: "uppercase" }}>Прогрес генерації</div>
          <div style={{ display: "grid", gap: "0.4rem" }}>
            {progressMessages.map((message, index) => (
              <div
                key={`${index}-${message}`}
                style={{
                  fontSize: "0.85rem",
                  color: "#cbd5e1",
                  padding: "0.45rem 0.7rem",
                  background: "#0f1210",
                  borderRadius: "6px",
                  border: "1px solid #1e2923",
                }}
              >
                <span style={{ color: "#14b8a6", fontWeight: 700, marginRight: "0.4rem" }}>{index + 1}.</span>
                {message}
              </div>
            ))}
          </div>
        </div>
      )}

      <label className="field-group" style={{ marginTop: "1.5rem" }}>
        <span>Результат асистента</span>
        <textarea
          rows={5}
          value={assistantMessage || ""}
          readOnly
          placeholder="Тут з'явиться підсумок від асистента."
        />
      </label>

      {(metrics?.tokensUsed || metrics?.draftTime || metrics?.llmTime) && (
        <div style={{ marginTop: "0.75rem", padding: "0.75rem 1rem", background: "#181a19", borderRadius: "8px", border: "1px solid #14b8a6", display: "flex", flexWrap: "wrap", gap: "1.5rem", fontSize: "0.85rem", color: "#94a3b8" }}>
          {metrics?.llmTime && (
            <div>Час генерації LLM: <strong style={{ color: "#e2e8f0" }}>{metrics.llmTime} сек</strong></div>
          )}
          {metrics?.draftTime && (
            <div>Загальний час: <strong style={{ color: "#e2e8f0" }}>{metrics.draftTime} сек</strong></div>
          )}
          {metrics?.tokensUsed && (
            <div>Токени: <strong style={{ color: "#e2e8f0" }}>{metrics.tokensUsed}</strong></div>
          )}
        </div>
      )}
    </section>
  );
}
