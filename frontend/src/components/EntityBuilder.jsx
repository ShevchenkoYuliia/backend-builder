import { useProjectStore } from "../store/projectStore";

const FIELD_TYPES = ["string", "integer", "float", "boolean", "datetime", "text"];
const RELATION_TYPES = ["many_to_one", "one_to_many", "many_to_many", "one_to_one"];
const HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"];

const parseDefaultValue = (rawValue, type) => {
  if (rawValue === "") {
    return null;
  }
  if (type === "integer") {
    const parsed = Number.parseInt(rawValue, 10);
    return Number.isNaN(parsed) ? rawValue : parsed;
  }
  if (type === "float") {
    const parsed = Number.parseFloat(rawValue);
    return Number.isNaN(parsed) ? rawValue : parsed;
  }
  if (type === "boolean") {
    return rawValue === "true";
  }
  return rawValue;
};

const stringifyDefaultValue = (value) => {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
};

export default function EntityBuilder({ entityIdx, entityOptions }) {
  const {
    project,
    updateEntity,
    addField,
    updateField,
    removeField,
    addRelation,
    updateRelation,
    removeRelation,
    addCustomEndpoint,
    updateCustomEndpoint,
    removeCustomEndpoint,
  } = useProjectStore();

  const entity = project.entities[entityIdx];
  if (!entity) {
    return (
      <section className="panel panel-soft empty-panel">
        <h3>Оберіть сутність</h3>
        <p>Додайте entity зліва, щоб налаштувати її поля, зв'язки та AI-ендпоінти.</p>
      </section>
    );
  }

  return (
    <section className="builder-stack">
      <article className="panel">
        <div className="section-header">
          <div>
            <span className="eyebrow">Entity</span>
            <h2>{entity.name || "Нова сутність"}</h2>
          </div>
          <div className="chip">{entity.fields.length} fields</div>
        </div>
        <label className="field-group">
          <span>Назва сутності</span>
          <input
            value={entity.name}
            onChange={(event) => updateEntity(entityIdx, { name: event.target.value })}
            placeholder="Наприклад Product"
          />
        </label>
      </article>

      <article className="panel">
        <div className="section-header">
          <div>
            <span className="eyebrow">Schema</span>
            <h3>Поля</h3>
          </div>
          <button className="ghost-button" onClick={() => addField(entityIdx)}>
            + Додати поле
          </button>
        </div>

        <div className="field-list">
          {entity.fields.map((field, fieldIdx) => (
            <div key={`${field.name}-${fieldIdx}`} className="field-card">
              <div className="field-card-grid">
                <label className="field-group">
                  <span>Назва</span>
                  <input
                    value={field.name}
                    onChange={(event) =>
                      updateField(entityIdx, fieldIdx, { name: event.target.value })
                    }
                    placeholder="title"
                  />
                </label>

                <label className="field-group">
                  <span>Тип</span>
                  <select
                    value={field.type}
                    onChange={(event) =>
                      updateField(entityIdx, fieldIdx, { type: event.target.value })
                    }
                  >
                    {FIELD_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field-group">
                  <span>Default</span>
                  {field.type === "boolean" ? (
                    <select
                      value={field.default === null ? "" : String(field.default)}
                      onChange={(event) =>
                        updateField(entityIdx, fieldIdx, {
                          default:
                            event.target.value === ""
                              ? null
                              : event.target.value === "true",
                        })
                      }
                    >
                      <option value="">None</option>
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  ) : (
                    <input
                      value={stringifyDefaultValue(field.default)}
                      onChange={(event) =>
                        updateField(entityIdx, fieldIdx, {
                          default: parseDefaultValue(event.target.value, field.type),
                        })
                      }
                      placeholder="Опційно"
                    />
                  )}
                </label>

                <label className="field-group field-group-wide">
                  <span>Опис поля</span>
                  <input
                    value={field.description ?? ""}
                    onChange={(event) =>
                      updateField(entityIdx, fieldIdx, {
                        description: event.target.value,
                      })
                    }
                    placeholder="Короткий контекст для майбутньої API або команди"
                  />
                </label>
              </div>

              <div className="toggle-row">
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={field.required}
                    onChange={(event) =>
                      updateField(entityIdx, fieldIdx, {
                        required: event.target.checked,
                      })
                    }
                  />
                  Required
                </label>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={field.unique}
                    onChange={(event) =>
                      updateField(entityIdx, fieldIdx, {
                        unique: event.target.checked,
                      })
                    }
                  />
                  Unique
                </label>
                <button
                  className="danger-button"
                  onClick={() => removeField(entityIdx, fieldIdx)}
                >
                  Видалити
                </button>
              </div>
            </div>
          ))}
        </div>
      </article>

      <article className="panel">
        <div className="section-header">
          <div>
            <span className="eyebrow">Relations</span>
            <h3>Зв'язки між сутностями</h3>
          </div>
          <button className="ghost-button" onClick={() => addRelation(entityIdx)}>
            + Додати зв'язок
          </button>
        </div>

        <div className="field-list">
          {entity.relations.length === 0 ? (
            <div className="empty-inline">
              Поки що без зв'язків. Додайте relation для One-to-Many або Many-to-Many
              сценаріїв.
            </div>
          ) : null}

          {entity.relations.map((relation, relationIdx) => (
            <div key={`${relation.name}-${relationIdx}`} className="field-card">
              <div className="field-card-grid relation-grid">
                <label className="field-group">
                  <span>Alias</span>
                  <input
                    value={relation.name}
                    onChange={(event) =>
                      updateRelation(entityIdx, relationIdx, {
                        name: event.target.value,
                      })
                    }
                    placeholder="category"
                  />
                </label>

                <label className="field-group">
                  <span>Тип зв'язку</span>
                  <select
                    value={relation.relation_type}
                    onChange={(event) =>
                      updateRelation(entityIdx, relationIdx, {
                        relation_type: event.target.value,
                      })
                    }
                  >
                    {RELATION_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field-group">
                  <span>Цільова сутність</span>
                  <select
                    value={relation.target_entity}
                    onChange={(event) =>
                      updateRelation(entityIdx, relationIdx, {
                        target_entity: event.target.value,
                      })
                    }
                  >
                    <option value="">Оберіть entity</option>
                    {entityOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="toggle-row">
                <div className="helper-text">
                  Генератор збереже цей зв'язок у DSL та прокине його в згенерований API.
                </div>
                <button
                  className="danger-button"
                  onClick={() => removeRelation(entityIdx, relationIdx)}
                >
                  Видалити
                </button>
              </div>
            </div>
          ))}
        </div>
      </article>

      <article className="panel">
        <div className="section-header">
          <div>
            <span className="eyebrow">AI Logic</span>
            <h3>Кастомні ендпоінти</h3>
          </div>
          <button className="ghost-button" onClick={() => addCustomEndpoint(entityIdx)}>
            + Додати AI-ендпоінт
          </button>
        </div>

        <div className="field-list">
          {entity.custom_endpoints.length === 0 ? (
            <div className="empty-inline">
              Напишіть задачу природною мовою, і генератор створить слот під нестандартну
              логіку.
            </div>
          ) : null}

          {entity.custom_endpoints.map((endpoint, endpointIdx) => (
            <div key={`${endpoint.method}-${endpointIdx}`} className="field-card">
              <div className="field-card-grid endpoint-grid">
                <label className="field-group">
                  <span>HTTP метод</span>
                  <select
                    value={endpoint.method}
                    onChange={(event) =>
                      updateCustomEndpoint(entityIdx, endpointIdx, {
                        method: event.target.value,
                      })
                    }
                  >
                    {HTTP_METHODS.map((method) => (
                      <option key={method} value={method}>
                        {method}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field-group">
                  <span>Path</span>
                  <input
                    value={endpoint.path}
                    onChange={(event) =>
                      updateCustomEndpoint(entityIdx, endpointIdx, {
                        path: event.target.value,
                      })
                    }
                    placeholder="/top-products"
                  />
                </label>

                <label className="field-group field-group-wide">
                  <span>Prompt для AI</span>
                  <textarea
                    value={endpoint.description}
                    onChange={(event) =>
                      updateCustomEndpoint(entityIdx, endpointIdx, {
                        description: event.target.value,
                      })
                    }
                    rows={4}
                    placeholder="Наприклад: створи ендпоінт, який повертає 5 найдорожчих товарів у цій категорії"
                  />
                </label>
              </div>

              {endpoint.code && (
                <div style={{ marginTop: "0.5rem", marginBottom: "0.75rem", borderTop: "1px dashed #1e2923", paddingTop: "0.75rem", width: "100%" }}>
                  <span style={{ fontSize: "0.75rem", color: "#64748b", textTransform: "uppercase", display: "block", marginBottom: "0.35rem", letterSpacing: "0.05em" }}>
                    Згенерований код API:
                  </span>
                  <pre style={{ background: "#060807", padding: "0.85rem", borderRadius: "6px", fontSize: "0.82rem", color: "#10b981", overflowX: "auto", border: "1px solid #10b98133", fontFamily: "monospace", margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                    {endpoint.code}
                  </pre>
                </div>
              )}

              <div className="toggle-row">
                <div className="helper-text">
                  ШІ генерує лише тіло функції, а каркас роутера й інфраструктуру контролюють
                  шаблони.
                </div>
                <button
                  className="danger-button"
                  onClick={() => removeCustomEndpoint(entityIdx, endpointIdx)}
                >
                  Видалити
                </button>
              </div>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}
