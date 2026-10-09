import React from "react";

export default function ArchitectureTables({ project }) {
  if (!project || !project.entities || project.entities.length === 0) {
    return <div className="empty-inline">Немає сутностей для відображення.</div>;
  }

  return (
    <div className="architecture-tables">
      {project.entities.map((entity, idx) => (
        <div key={`${entity.name}-${idx}`} className="db-table-card">
          <div className="db-table-header">
            <h4>{entity.name || `Entity ${idx + 1}`}</h4>
          </div>
          
          <table className="db-table">
            <thead>
              <tr>
                <th>Поле</th>
                <th>Тип</th>
                <th>Властивості</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>id</strong> 🔑</td>
                <td>UUID / ObjectId</td>
                <td>PK, Required, Unique</td>
              </tr>
              {entity.fields && entity.fields.map((field, fIdx) => (
                <tr key={`${field.name}-${fIdx}`}>
                  <td><strong>{field.name}</strong></td>
                  <td>{field.type}</td>
                  <td>
                    <span className="field-props">
                      {field.required && <span className="prop-badge req">Req</span>}
                      {field.unique && <span className="prop-badge uniq">Uniq</span>}
                      {field.default !== null && field.default !== "" && (
                        <span className="prop-badge def">Def: {String(field.default)}</span>
                      )}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {entity.relations && entity.relations.length > 0 && (
            <div className="db-relations">
              <strong>Зв'язки:</strong>
              <ul>
                {entity.relations.map((rel, rIdx) => (
                  <li key={`${rel.name}-${rIdx}`}>
                    <span className="rel-type">{rel.relation_type}</span> → <strong>{rel.target_entity}</strong> 
                    <span className="rel-alias"> (alias: {rel.name})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
