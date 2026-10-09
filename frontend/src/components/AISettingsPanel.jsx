const MODEL_OPTIONS = {
  openai: ["gpt-5-mini", "gpt-5.2", "gpt-4.1", "gpt-4o-mini"],
  ollama: ["llama3.1", "mistral", "phi3:mini"],
  gemini: ["gemini-2.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"],
  claude: [
    "claude-sonnet-4-20250514",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
  ],
  custom: ["gpt-4o-mini", "llama3.1", "custom-model"],
};

const PROVIDER_LABELS = {
  openai: "OpenAI (cloud)",
  ollama: "Ollama (local, no key)",
  gemini: "Gemini (Google AI Studio)",
  claude: "Claude (Anthropic)",
  custom: "Custom API (OpenAI-compatible)",
};

const needsApiKey = (provider) => provider !== "ollama";

export default function AISettingsPanel({
  settings,
  form,
  loading,
  onChange,
  onSave,
  onDeleteKey,
}) {
  const provider = form.provider || "openai";
  const keyRequired = needsApiKey(provider);

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <span className="eyebrow">AI Settings</span>
          <h3>LLM provider</h3>
        </div>
        <div className={`chip ${settings.api_key_present ? "chip-success" : "chip-danger"}`}>
          {settings.api_key_present ? "key saved" : keyRequired ? "key missing" : "no key needed"}
        </div>
      </div>

      <div className="field-list">
        <label className="field-group">
          <span>Provider</span>
          <select
            value={provider}
            onChange={(event) => {
              const nextProvider = event.target.value;
              onChange("provider", nextProvider);
              onChange("model", MODEL_OPTIONS[nextProvider]?.[0] || "");
            }}
          >
            {Object.entries(PROVIDER_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className="field-group">
          <span>Model</span>
          {provider === "custom" ? (
            <input
              value={form.model}
              onChange={(event) => onChange("model", event.target.value)}
              placeholder="model-name"
            />
          ) : (
            <select value={form.model} onChange={(event) => onChange("model", event.target.value)}>
              {(MODEL_OPTIONS[provider] || []).map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          )}
        </label>

        {provider === "custom" && (
          <label className="field-group">
            <span>Base URL</span>
            <input
              value={form.base_url || ""}
              onChange={(event) => onChange("base_url", event.target.value)}
              placeholder="https://your-provider.example/v1"
            />
          </label>
        )}

        <label className="field-group">
          <span>API key</span>
          <input
            type="password"
            value={form.api_key}
            onChange={(event) => onChange("api_key", event.target.value)}
            disabled={!keyRequired}
            placeholder={
              !keyRequired
                ? "Ollama does not need an API key"
                : settings.api_key_present
                  ? `Saved: ${settings.api_key_masked ?? "hidden"}`
                  : "Paste API key for the selected provider"
            }
          />
        </label>

        <div className="toggle-row">
          <button className="primary-button" disabled={loading} onClick={onSave}>
            {loading ? "Saving..." : "Save AI settings"}
          </button>
          <button
            className="ghost-button"
            disabled={loading || !settings.api_key_present}
            onClick={onDeleteKey}
          >
            Delete key
          </button>
        </div>
      </div>
    </section>
  );
}
