import axios from "axios";

export const SESSION_STORAGE_KEY = "builder-session";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000/api",
});

let accessTokenValue = "";

export const setAccessToken = (token) => {
  accessTokenValue = token;
  api.defaults.headers.common.Authorization = `Bearer ${token}`;
};

export const clearAccessToken = () => {
  accessTokenValue = "";
  delete api.defaults.headers.common.Authorization;
};

export const registerUser = async (payload) => {
  const { data } = await api.post("/auth/register", payload);
  return data;
};

export const loginUser = async (payload) => {
  const { data } = await api.post("/auth/login", payload);
  return data;
};

export const getCurrentUser = async () => {
  const { data } = await api.get("/auth/me");
  return data;
};

export const getAISettings = async () => {
  const { data } = await api.get("/ai-settings/");
  return data;
};

export const updateAISettings = async (payload) => {
  const { data } = await api.put("/ai-settings/", payload);
  return data;
};

export const deleteAIKey = async () => {
  const { data } = await api.delete("/ai-settings/key");
  return data;
};

export const generateAssistantDraft = async (payload, options = {}) => {
  const response = await fetch(`${api.defaults.baseURL}/assistant/draft`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessTokenValue ? { Authorization: `Bearer ${accessTokenValue}` } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorBody = null;
    try {
      errorBody = await response.json();
    } catch {
      errorBody = null;
    }
    const error = new Error(
      errorBody?.detail || `Request failed with status ${response.status}.`
    );
    error.response = { data: errorBody ?? { detail: error.message } };
    throw error;
  }

  if (!response.body) {
    throw new Error("Empty response body from assistant draft stream.");
  }

  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.trim()) {
        continue;
      }
      const event = JSON.parse(line);
      if (event.type === "progress") {
        options.onProgress?.(event.message);
        continue;
      }
      if (event.type === "error") {
        const error = new Error(
          typeof event.detail === "string"
            ? event.detail
            : event.detail?.message || "Could not generate project draft."
        );
        error.response = { data: { detail: event.detail } };
        throw error;
      }
      if (event.type === "result") {
        return event.data;
      }
    }
  }

  throw new Error("Assistant draft stream ended without a final result.");
};

export const getAssistantHistory = async () => {
  const { data } = await api.get("/assistant/history");
  return data;
};

export const getAssistantHistoryItem = async (id) => {
  const { data } = await api.get(`/assistant/history/${id}`);
  return data;
};

export const getProjects = async () => {
  const { data } = await api.get("/projects/");
  return data;
};

export const getProject = async (id) => {
  const { data } = await api.get(`/projects/${id}`);
  return data;
};

export const createProject = async (payload) => {
  const { data } = await api.post("/projects/", payload);
  return data;
};

export const updateProject = async (id, payload) => {
  const { data } = await api.put(`/projects/${id}`, payload);
  return data;
};

export const deleteProject = async (id) => {
  const { data } = await api.delete(`/projects/${id}`);
  return data;
};

export const validateProject = async (payload) => {
  const { data } = await api.post("/validate/", payload);
  return data;
};

export const generateProject = async (projectData) => {
  const response = await api.post("/generate/", projectData, {
    responseType: "blob",
  });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${projectData.name}_backend.zip`;
  anchor.click();
  URL.revokeObjectURL(url);
  
  return {
    generationTime: response.headers["x-generation-time-sec"],
    compileSuccess: response.headers["x-compile-success"] === "true",
  };
};

export const deployProject = async (projectData) => {
  const { data } = await api.post("/generate/deploy", projectData);
  return data;
};

export const generateCustomEndpoints = async (projectData) => {
  const { data } = await api.post("/generate/endpoints", projectData);
  return data;
};

export const extractApiError = (error, fallback = "Something went wrong.") => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (detail?.message) {
    return detail.message;
  }
  if (error?.message) {
    return error.message;
  }
  return fallback;
};
