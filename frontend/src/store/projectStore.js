import { create } from "zustand";

export const createEmptyField = () => ({
  name: "field_name",
  type: "string",
  required: true,
  unique: false,
  default: null,
  description: "",
});

export const createEmptyRelation = () => ({
  name: "relation_name",
  target_entity: "",
  relation_type: "many_to_one",
});

export const createEmptyEndpoint = () => ({
  method: "GET",
  path: "/custom-action",
  description: "",
  code: null,
});

export const createEmptyEntity = (name = "Entity") => ({
  name,
  fields: [createEmptyField()],
  relations: [],
  custom_endpoints: [],
});

export const createEmptyProject = () => ({
  name: "Builder",
  description: "Visual DSL for a generated backend service.",
  db_type: "postgresql",
  include_auth: false,
  entities: [createEmptyEntity("Product")],
});

const normalizeProject = (project = {}) => ({
  name: project.name ?? "Builder",
  description: project.description ?? "",
  db_type: project.db_type ?? "postgresql",
  include_auth: project.include_auth ?? false,
  entities: (project.entities ?? []).map((entity, index) => ({
    name: entity.name ?? `Entity${index + 1}`,
    fields: (entity.fields ?? []).map((field) => ({
      ...createEmptyField(),
      ...field,
    })),
    relations: (entity.relations ?? []).map((relation) => ({
      ...createEmptyRelation(),
      ...relation,
    })),
    custom_endpoints: (entity.custom_endpoints ?? []).map((endpoint) => ({
      ...createEmptyEndpoint(),
      code: endpoint.code ?? null,
      ...endpoint,
    })),
  })),
});

export const toProjectPayload = (project) => normalizeProject(project);

export const useProjectStore = create((set) => ({
  project: createEmptyProject(),
  selectedEntityIdx: 0,

  loadProject: (project) =>
    set(() => {
      const normalized = normalizeProject(project);
      return {
        project: normalized,
        selectedEntityIdx: normalized.entities.length ? 0 : null,
      };
    }),

  reset: () =>
    set(() => ({
      project: createEmptyProject(),
      selectedEntityIdx: 0,
    })),

  setProjectMeta: (patch) =>
    set((state) => ({
      project: { ...state.project, ...patch },
    })),

  selectEntity: (idx) => set({ selectedEntityIdx: idx }),

  addEntity: () =>
    set((state) => {
      const nextIndex = state.project.entities.length + 1;
      const entities = [
        ...state.project.entities,
        createEmptyEntity(`Entity${nextIndex}`),
      ];
      return {
        project: { ...state.project, entities },
        selectedEntityIdx: entities.length - 1,
      };
    }),

  removeEntity: (idx) =>
    set((state) => {
      const entities = state.project.entities.filter((_, index) => index !== idx);
      return {
        project: { ...state.project, entities },
        selectedEntityIdx: entities.length ? Math.max(0, idx - 1) : null,
      };
    }),

  updateEntity: (idx, patch) =>
    set((state) => ({
      project: {
        ...state.project,
        entities: state.project.entities.map((entity, index) =>
          index === idx ? { ...entity, ...patch } : entity
        ),
      },
    })),

  addField: (entityIdx) =>
    set((state) => ({
      project: {
        ...state.project,
        entities: state.project.entities.map((entity, index) =>
          index === entityIdx
            ? { ...entity, fields: [...entity.fields, createEmptyField()] }
            : entity
        ),
      },
    })),

  updateField: (entityIdx, fieldIdx, patch) =>
    set((state) => ({
      project: {
        ...state.project,
        entities: state.project.entities.map((entity, index) =>
          index === entityIdx
            ? {
                ...entity,
                fields: entity.fields.map((field, innerIndex) =>
                  innerIndex === fieldIdx ? { ...field, ...patch } : field
                ),
              }
            : entity
        ),
      },
    })),

  removeField: (entityIdx, fieldIdx) =>
    set((state) => ({
      project: {
        ...state.project,
        entities: state.project.entities.map((entity, index) =>
          index === entityIdx
            ? {
                ...entity,
                fields: entity.fields.filter((_, innerIndex) => innerIndex !== fieldIdx),
              }
            : entity
        ),
      },
    })),

  addRelation: (entityIdx) =>
    set((state) => ({
      project: {
        ...state.project,
        entities: state.project.entities.map((entity, index) =>
          index === entityIdx
            ? { ...entity, relations: [...entity.relations, createEmptyRelation()] }
            : entity
        ),
      },
    })),

  updateRelation: (entityIdx, relationIdx, patch) =>
    set((state) => ({
      project: {
        ...state.project,
        entities: state.project.entities.map((entity, index) =>
          index === entityIdx
            ? {
                ...entity,
                relations: entity.relations.map((relation, innerIndex) =>
                  innerIndex === relationIdx ? { ...relation, ...patch } : relation
                ),
              }
            : entity
        ),
      },
    })),

  removeRelation: (entityIdx, relationIdx) =>
    set((state) => ({
      project: {
        ...state.project,
        entities: state.project.entities.map((entity, index) =>
          index === entityIdx
            ? {
                ...entity,
                relations: entity.relations.filter(
                  (_, innerIndex) => innerIndex !== relationIdx
                ),
              }
            : entity
        ),
      },
    })),

  addCustomEndpoint: (entityIdx) =>
    set((state) => ({
      project: {
        ...state.project,
        entities: state.project.entities.map((entity, index) =>
          index === entityIdx
            ? {
                ...entity,
                custom_endpoints: [...entity.custom_endpoints, createEmptyEndpoint()],
              }
            : entity
        ),
      },
    })),

  updateCustomEndpoint: (entityIdx, endpointIdx, patch) =>
    set((state) => ({
      project: {
        ...state.project,
        entities: state.project.entities.map((entity, index) =>
          index === entityIdx
            ? {
                ...entity,
                custom_endpoints: entity.custom_endpoints.map((endpoint, innerIndex) =>
                  innerIndex === endpointIdx ? { ...endpoint, ...patch } : endpoint
                ),
              }
            : entity
        ),
      },
    })),

  removeCustomEndpoint: (entityIdx, endpointIdx) =>
    set((state) => ({
      project: {
        ...state.project,
        entities: state.project.entities.map((entity, index) =>
          index === entityIdx
            ? {
                ...entity,
                custom_endpoints: entity.custom_endpoints.filter(
                  (_, innerIndex) => innerIndex !== endpointIdx
                ),
              }
            : entity
        ),
      },
    })),
}));
