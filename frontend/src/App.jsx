import { startTransition, useDeferredValue, useEffect, useState } from "react";

import {
  clearAccessToken,
  createProject,
  deleteAIKey,
  deleteProject,
  deployProject,
  generateCustomEndpoints,
  extractApiError,
  generateAssistantDraft,
  generateProject,
  getAISettings,
  getAssistantHistory,
  getAssistantHistoryItem,
  getCurrentUser,
  getProject,
  getProjects,
  loginUser,
  registerUser,
  SESSION_STORAGE_KEY,
  setAccessToken,
  updateAISettings,
  updateProject,
  validateProject,
} from "./api/client";
import AISettingsPanel from "./components/AISettingsPanel";
import ArchitectureDiagram from "./components/ArchitectureDiagram";
import AuthScreen from "./components/AuthScreen";
import ChatHistoryPanel from "./components/ChatHistoryPanel";
import EntityBuilder from "./components/EntityBuilder";
import IdeaPanel from "./components/IdeaPanel";
import StatsPanel from "./components/StatsPanel";
import ValidationPanel from "./components/ValidationPanel";
import ArchitectureTables from "./components/ArchitectureTables";
import { toProjectPayload, useProjectStore } from "./store/projectStore";

const DB_TYPES = ["postgresql", "mysql", "mongodb"];

const emptyValidationReport = () => ({ valid: true, issues: [] });

const emptySettings = () => ({
  provider: "openai",
  model: "gpt-5-mini",
  base_url: "",
  api_key_present: false,
  api_key_masked: null,
  updated_at: null,
});

const loadStoredSession = () => {
  try {
    const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const saveSession = (session) => {
  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
};

const clearSession = () => {
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
};

const validationFromError = (error) => {
  const detail = error?.response?.data?.detail;
  if (detail?.issues) {
    return { valid: false, issues: detail.issues };
  }
  return {
    valid: false,
    issues: [
      {
        severity: "error",
        code: "request.failed",
        message: extractApiError(error, "Validation failed."),
        location: [],
      },
    ],
  };
};

const STATS_KEY = "builder-stats";

const numericMetric = (value) => {
  const parsed = parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const withComputedTotals = (record) => {
  const draftTime = numericMetric(record.draftTime);
  const generationTime = numericMetric(record.generationTime);
  const endpointsTime = numericMetric(record.endpointsTime);
  if (draftTime || generationTime || endpointsTime) {
    return {
      ...record,
      totalTime: parseFloat((draftTime + generationTime + endpointsTime).toFixed(2)),
    };
  }
  return record;
};

const upsertStatsRecord = (record) => {
  try {
    const existing = JSON.parse(window.localStorage.getItem(STATS_KEY) || "[]");
    const prompt = record.prompt ?? "";
    const recordIndex = existing.findIndex((item) => item.prompt === prompt);
    const normalizedRecord = withComputedTotals(record);
    if (recordIndex !== -1) {
      existing[recordIndex] = withComputedTotals({
        ...existing[recordIndex],
        ...normalizedRecord,
        failedAttempts: Math.max(
          normalizedRecord.failedAttempts ?? 0,
          existing[recordIndex].failedAttempts ?? 0
        ),
      });
    } else {
      existing.unshift({
        failedAttempts: 0,
        ...normalizedRecord,
      });
    }
    window.localStorage.setItem(STATS_KEY, JSON.stringify(existing.slice(0, 100)));
  } catch {
    // ignore local storage errors
  }
};

export default function App() {
  const {
    project,
    selectedEntityIdx,
    setProjectMeta,
    addEntity,
    removeEntity,
    selectEntity,
    loadProject,
    reset,
  } = useProjectStore();

  const [session, setSession] = useState(loadStoredSession);
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState({
    full_name: "",
    email: "",
    password: "",
  });
  const [authError, setAuthError] = useState("");
  const [settings, setSettings] = useState(emptySettings());
  const [settingsForm, setSettingsForm] = useState({
    provider: "openai",
    model: "gpt-5-mini",
    base_url: "",
    api_key: "",
  });
  const [history, setHistory] = useState([]);
  const [projects, setProjects] = useState([]);
  const [activeProjectId, setActiveProjectId] = useState(null);
  const [activeChatId, setActiveChatId] = useState(null);
  const [ideaPrompt, setIdeaPrompt] = useState("");
  const [assistantMessage, setAssistantMessage] = useState("");
  const [draftProgress, setDraftProgress] = useState([]);
  const [lastMetrics, setLastMetrics] = useState(null);
  const [status, setStatus] = useState("");
  const [deployUrl, setDeployUrl] = useState("");
  const [previewMode, setPreviewMode] = useState("diagram");
  const [activeTab, setActiveTab] = useState("workspace");
  const [validationReport, setValidationReport] = useState(emptyValidationReport());
  const [loading, setLoading] = useState({
    auth: false,
    bootstrap: true,
    draft: false,
    history: false,
    save: false,
    generate: false,
    deploy: false,
    endpoints: false,
    validation: false,
    settings: false,
  });

  const [endpointsSeconds, setEndpointsSeconds] = useState(0);

  useEffect(() => {
    let interval = null;
    if (loading.endpoints) {
      interval = setInterval(() => {
        setEndpointsSeconds((s) => s + 1);
      }, 1000);
    } else {
      setEndpointsSeconds(0);
    }
    return () => clearInterval(interval);
  }, [loading.endpoints]);

  const deferredProject = useDeferredValue(project);

  const stats = {
    entities: project.entities.length,
    fields: project.entities.reduce((sum, entity) => sum + entity.fields.length, 0),
    relations: project.entities.reduce(
      (sum, entity) => sum + entity.relations.length,
      0
    ),
    endpoints: project.entities.reduce(
      (sum, entity) => sum + entity.custom_endpoints.length,
      0
    ),
  };

  const refreshWorkspaceData = async () => {
    const [settingsData, historyData, projectsData] = await Promise.all([
      getAISettings(),
      getAssistantHistory(),
      getProjects(),
    ]);
    setSettings(settingsData);
    setSettingsForm((current) => ({
      provider: settingsData.provider ?? current.provider,
      model: settingsData.model ?? current.model,
      base_url: settingsData.base_url ?? "",
      api_key: "",
    }));
    setHistory(historyData.items ?? []);
    setProjects(projectsData);
  };

  useEffect(() => {
    const bootstrap = async () => {
      if (!session?.access_token) {
        clearAccessToken();
        return;
      }

      setLoading((current) => ({ ...current, bootstrap: true }));
      try {
        setAccessToken(session.access_token);
        const user = await getCurrentUser();
        const nextSession = { ...session, user };
        saveSession(nextSession);
        setSession(nextSession);
        await refreshWorkspaceData();
      } catch {
        clearAccessToken();
        clearSession();
        setSession(null);
      } finally {
        setLoading((current) => ({ ...current, bootstrap: false }));
      }
    };

    bootstrap();
  }, []);

  useEffect(() => {
    if (!session?.access_token) {
      return undefined;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setLoading((current) => ({ ...current, validation: true }));
      try {
        const report = await validateProject(toProjectPayload(project));
        if (!cancelled) {
          setValidationReport(report);
        }
      } catch (error) {
        if (!cancelled) {
          setValidationReport(validationFromError(error));
        }
      } finally {
        if (!cancelled) {
          setLoading((current) => ({ ...current, validation: false }));
        }
      }
    }, 450);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [project, session?.access_token]);

  const handleAuthFieldChange = (field, value) => {
    setAuthForm((current) => ({ ...current, [field]: value }));
  };

  const handleAuthSubmit = async (event) => {
    event.preventDefault();
    setLoading((current) => ({ ...current, auth: true }));
    setAuthError("");

    try {
      const response =
        authMode === "login"
          ? await loginUser({
            email: authForm.email,
            password: authForm.password,
          })
          : await registerUser(authForm);

      setAccessToken(response.access_token);
      const nextSession = { access_token: response.access_token, user: response.user };
      saveSession(nextSession);
      setSession(nextSession);
      setAuthForm({ full_name: "", email: "", password: "" });
      await refreshWorkspaceData();
      setStatus("Вхід виконано. Тепер можна додати AI key та згенерувати структуру з ідеї.");
    } catch (error) {
      setAuthError(extractApiError(error, "Could not complete authentication."));
    } finally {
      setLoading((current) => ({ ...current, auth: false }));
    }
  };

  const handleLogout = () => {
    clearAccessToken();
    clearSession();
    setSession(null);
    setSettings(emptySettings());
    setHistory([]);
    setProjects([]);
    setActiveProjectId(null);
    setActiveChatId(null);
    setAssistantMessage("");
    setDraftProgress([]);
    setLastMetrics(null);
    setDeployUrl("");
    setIdeaPrompt("");
    setValidationReport(emptyValidationReport());
    startTransition(() => reset());
  };

  const handleNewChat = () => {
    setActiveChatId(null);
    setIdeaPrompt("");
    setAssistantMessage("");
    setDraftProgress([]);
    setLastMetrics(null);
    setDeployUrl("");
    setValidationReport(emptyValidationReport());
    startTransition(() => reset());
  };


  const handleSettingsChange = (field, value) => {
    setSettingsForm((current) => ({ ...current, [field]: value }));
  };

  const handleSaveSettings = async () => {
    setLoading((current) => ({ ...current, settings: true }));
    try {
      const payload = {
        provider: settingsForm.provider,
        model: settingsForm.model,
        base_url: settingsForm.provider === "custom" ? settingsForm.base_url.trim() : null,
      };
      if (settingsForm.api_key.trim()) {
        payload.api_key = settingsForm.api_key.trim();
      }
      const saved = await updateAISettings(payload);
      setSettings(saved);
      setSettingsForm((current) => ({
        ...current,
        api_key: "",
        model: saved.model,
        base_url: saved.base_url ?? "",
      }));
      setStatus("Налаштування AI оновлено.");
    } catch (error) {
      setStatus(extractApiError(error, "Не вдалося зберегти налаштування AI."));
    } finally {
      setLoading((current) => ({ ...current, settings: false }));
    }
  };

  const handleDeleteKey = async () => {
    setLoading((current) => ({ ...current, settings: true }));
    try {
      await deleteAIKey();
      const refreshed = await getAISettings();
      setSettings(refreshed);
      setSettingsForm((current) => ({ ...current, api_key: "" }));
      setStatus("Ключ AI видалено.");
    } catch (error) {
      setStatus(extractApiError(error, "Не вдалося видалити ключ AI."));
    } finally {
      setLoading((current) => ({ ...current, settings: false }));
    }
  };

  const handleGenerateDraft = async () => {
    setLoading((current) => ({ ...current, draft: true, history: true }));
    setDraftProgress([]);
    try {
      const start = Date.now();
      const result = await generateAssistantDraft(
        { prompt: ideaPrompt },
        {
          onProgress: (message) => {
            setDraftProgress((current) => [...current, message]);
            setStatus(message);
          },
        }
      );
      const draftTime = ((Date.now() - start) / 1000).toFixed(1);
      startTransition(() => loadProject(result.project));
      setAssistantMessage(result.assistant_message);
      const projectSnapshot = result.project;
      const entitiesCount = projectSnapshot?.entities?.length ?? 0;
      const fieldsCount = (projectSnapshot?.entities ?? []).reduce((s, e) => s + (e.fields?.length ?? 0), 0);
      const relationsCount = (projectSnapshot?.entities ?? []).reduce((s, e) => s + (e.relations?.length ?? 0), 0);
      const newMetrics = {
        type: "draft",
        tokensUsed: result.tokens_used,
        draftTime,
        totalTime: parseFloat(draftTime),
        llmTime: result.llm_time ?? null,
        failedAttempts: result.failed_attempts ?? 0,
        prompt: ideaPrompt,
        model: result.model || settings.model,
        dbType: projectSnapshot?.db_type ?? project.db_type,
        entitiesCount,
        fieldsCount,
        relationsCount,
        timestamp: new Date().toISOString(),
      };
      setLastMetrics(newMetrics);
      upsertStatsRecord(newMetrics);
      setActiveChatId(result.chat_id);
      setActiveProjectId(null);
      setValidationReport(emptyValidationReport());
      const historyData = await getAssistantHistory();
      setHistory(historyData.items ?? []);
      setStatus("AI підготував сутності, поля та endpoints. Тепер можна відредагувати проєкт вручну.");
    } catch (error) {
      setStatus(extractApiError(error, "Не вдалося згенерувати чернетку."));
      try {
        const historyData = await getAssistantHistory();
        setHistory(historyData.items ?? []);
        const failedItem = (historyData.items ?? []).find((item) => item.prompt === ideaPrompt);
        const failedMetrics = {
          type: "draft_error",
          prompt: ideaPrompt,
          model: failedItem?.model || settings.model,
          dbType: project.db_type,
          entitiesCount: stats.entities,
          fieldsCount: stats.fields,
          relationsCount: stats.relations,
          failedAttempts: failedItem?.failed_attempts ?? 1,
          tokensUsed: 0,
          timestamp: new Date().toISOString(),
        };
        setLastMetrics(failedMetrics);
        upsertStatsRecord(failedMetrics);
      } catch {
        // ignore history refresh errors
      }
    } finally {
      setLoading((current) => ({ ...current, draft: false, history: false }));
    }
  };

  const handleOpenHistoryItem = async (chatId) => {
    setLoading((current) => ({ ...current, history: true }));
    try {
      const item = await getAssistantHistoryItem(chatId);
      setIdeaPrompt(item.prompt);
      setAssistantMessage(item.assistant_message);
      setActiveChatId(item.id);
      startTransition(() => loadProject(item.project));
      setStatus("Історію чату відкрито та завантажено в конструктор.");
    } catch (error) {
      setStatus(extractApiError(error, "Не вдалося відкрити історію чату."));
    } finally {
      setLoading((current) => ({ ...current, history: false }));
    }
  };

  const handleLoadProject = async (projectId) => {
    try {
      const fullProject = await getProject(projectId);
      setActiveProjectId(fullProject.id);
      setActiveChatId(null);
      startTransition(() => loadProject(fullProject));
      setStatus(`Проєкт "${fullProject.name}" завантажено.`);
    } catch (error) {
      setStatus(extractApiError(error, "Не вдалося відкрити збережений проєкт."));
    }
  };

  const handleSaveProject = async () => {
    setLoading((current) => ({ ...current, save: true }));
    try {
      const payload = toProjectPayload(project);
      const savedProject = activeProjectId
        ? await updateProject(activeProjectId, payload)
        : await createProject(payload);
      setActiveProjectId(savedProject.id);
      const projectsData = await getProjects();
      setProjects(projectsData);
      setStatus("Проєкт збережено.");
    } catch (error) {
      setStatus(extractApiError(error, "Не вдалося зберегти проєкт."));
    } finally {
      setLoading((current) => ({ ...current, save: false }));
    }
  };

  const handleDeleteProject = async (projectId) => {
    try {
      await deleteProject(projectId);
      const projectsData = await getProjects();
      setProjects(projectsData);
      if (projectId === activeProjectId) {
        setActiveProjectId(null);
      }
      setStatus("Проєкт видалено.");
    } catch (error) {
      setStatus(extractApiError(error, "Не вдалося видалити проєкт."));
    }
  };

  const handleIssueClick = (issue) => {
    if (!issue?.location?.length) return;
    const loc = issue.location;
    // If the issue refers to the entities root (e.g. ["entities"]) — create a new entity and focus it
    if (loc.length === 1 && loc[0] === "entities") {
      setActiveTab("workspace");
      // addEntity sets selectedEntityIdx to the new entity automatically
      addEntity();
      return;
    }

    // location format: ["entities", "<idx>", "fields", "<idx>", ...]
    const entitiesKeyIdx = loc.indexOf("entities");
    if (entitiesKeyIdx !== -1 && loc.length > entitiesKeyIdx + 1) {
      const entityIdx = parseInt(loc[entitiesKeyIdx + 1], 10);
      if (!isNaN(entityIdx)) {
        setActiveTab("workspace");
        selectEntity(entityIdx);
      }
    }
  };

  const handleGenerateZip = async () => {
    setLoading((current) => ({ ...current, generate: true }));
    try {
      const payload = toProjectPayload(project);
      const report = await validateProject(payload);
      setValidationReport(report);
      if (!report.valid) {
        setStatus("Виправте помилки валідації перед експортом ZIP.");
        return;
      }
      const metrics = await generateProject(payload);
      const newMetrics = {
        type: "generate",
        prompt: ideaPrompt || project.name || "",
        model: settings.model,
        dbType: project.db_type,
        entitiesCount: stats.entities,
        fieldsCount: stats.fields,
        relationsCount: stats.relations,
        generationTime: metrics.generationTime,
        compileSuccess: true,
        timestamp: new Date().toISOString(),
      };
      setLastMetrics((prev) => {
        const updated = withComputedTotals({
          ...prev,
          ...newMetrics,
          failedAttempts: prev?.failedAttempts ?? 0,
        });
        delete updated.tokensUsed;
        return updated;
      });
      upsertStatsRecord(newMetrics);
      setStatus("ZIP згенеровано та завантажено.");
    } catch (error) {
      setValidationReport(validationFromError(error));
      setStatus(extractApiError(error, "Не вдалося згенерувати ZIP."));
    } finally {
      setLoading((current) => ({ ...current, generate: false }));
    }
  };

  const handleDeploy = async () => {
    setLoading((current) => ({ ...current, deploy: true }));
    setDeployUrl("");
    try {
      const payload = toProjectPayload(project);
      const report = await validateProject(payload);
      setValidationReport(report);
      if (!report.valid) {
        setStatus("Виправте помилки валідації перед розгортанням.");
        return;
      }
      const runDeploy = async () => {
        try {
          const result = await deployProject(payload);
          const deployMetrics = {
            type: "deploy",
            prompt: ideaPrompt || project.name || "",
            model: settings.model,
            dbType: project.db_type,
            entitiesCount: stats.entities,
            fieldsCount: stats.fields,
            relationsCount: stats.relations,
            generationTime: result.generationTime,
            compileSuccess: true,
            timestamp: new Date().toISOString(),
          };
          setLastMetrics((prev) => {
            const updated = withComputedTotals({
              ...prev,
              ...deployMetrics,
              failedAttempts: prev?.failedAttempts ?? 0,
            });
            delete updated.tokensUsed;
            return updated;
          });
          upsertStatsRecord(deployMetrics);
          setDeployUrl(result.url);
          setStatus(`Проєкт розгорнуто! OpenAPI доступний за посиланням нижче.`);
        } catch (error) {
          setStatus(extractApiError(error, "Не вдалося розгорнути проєкт."));
        } finally {
          setLoading((current) => ({ ...current, deploy: false }));
        }
      };
      await runDeploy();
    } catch (error) {
      setValidationReport(validationFromError(error));
      setStatus(extractApiError(error, "Перевірка перед розгортанням не вдалась."));
    } finally {
      setLoading((current) => ({ ...current, deploy: false }));
    }
  };

  const handleGenerateEndpoints = async () => {
    setLoading((current) => ({ ...current, endpoints: true }));
    try {
      const payload = toProjectPayload(project);
      const report = await validateProject(payload);
      setValidationReport(report);
      if (!report.valid) {
        setStatus("Виправте помилки валідації перед генерацією ендпоінтів.");
        return;
      }
      const result = await generateCustomEndpoints(payload);
      startTransition(() => loadProject(result.project));

      const endpointsMetrics = {
        type: "endpoints",
        prompt: ideaPrompt || project.name || "",
        model: settings.model,
        dbType: project.db_type,
        entitiesCount: stats.entities,
        fieldsCount: stats.fields,
        relationsCount: stats.relations,
        endpointsTime: result.time_spent,
        endpointsTokens: result.tokens_used,
        endpointsSuccess: result.success,
        timestamp: new Date().toISOString(),
      };

      setLastMetrics((prev) =>
        withComputedTotals({
          ...prev,
          ...endpointsMetrics,
          failedAttempts: prev?.failedAttempts ?? 0,
          tokensUsed: prev?.tokensUsed ?? 0,
        })
      );
      upsertStatsRecord(endpointsMetrics);

      if (result.success) {
        setStatus("AI ендпоінти успішно згенеровано! Тепер ви можете подивитися код або згенерувати ZIP.");
      } else {
        setStatus("Частина ендпоінтів згенерована з помилками (використано шаблони-заглушки).");
      }
    } catch (error) {
      setValidationReport(validationFromError(error));
      setStatus(extractApiError(error, "Не вдалося згенерувати AI ендпоінти."));
    } finally {
      setLoading((current) => ({ ...current, endpoints: false }));
    }
  };

  if (!session?.access_token) {
    return (
      <AuthScreen
        mode={authMode}
        form={authForm}
        loading={loading.auth}
        error={authError}
        onFieldChange={handleAuthFieldChange}
        onSubmit={handleAuthSubmit}
        onSwitchMode={() =>
          setAuthMode((current) => (current === "login" ? "register" : "login"))
        }
      />
    );
  }

  const entityOptions = project.entities.map((entity) => entity.name).filter(Boolean);
  const dslPreview = JSON.stringify(deferredProject, null, 2);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-block">
          <span className="eyebrow">Workspace</span>
          <h2>AI Builder</h2>
          <p className="muted">
            Ідея користувача автоматично трансформується AI у структурований
            DSL із сутностями та API для візуального конструктора.
          </p>
          <div className="security-panel">
            <strong>Безпека паролів</strong>
            <span>Хешування паролів з використанням PBKDF2-SHA256 та шифроване зберігання AI API ключів.</span>
          </div>
        </div>

        <AISettingsPanel
          settings={settings}
          form={settingsForm}
          loading={loading.settings}
          onChange={handleSettingsChange}
          onSave={handleSaveSettings}
          onDeleteKey={handleDeleteKey}
        />

        <ChatHistoryPanel
          history={history}
          activeChatId={activeChatId}
          loading={loading.history}
          onOpen={handleOpenHistoryItem}
          onNew={handleNewChat}
        />

        <div className="sidebar-actions">
          <button className="primary-button" onClick={handleLogout}>
            Вийти
          </button>
        </div>
      </aside>

      <main className="workspace">
        <section className="panel hero-panel">
          <div className="hero-panel-copy">
            <span className="eyebrow">AI-first flow</span>
            <h1>{project.name || "Нова AI чернетка"}</h1>
            <p>
              Згенерована моделлю структура відкривається у візуальному редакторі,
              де можна переглянути схему, доопрацювати її вручну та після генерації
              коду експортувати у ZIP або задеплоїти в Docker.
            </p>
          </div>
          <div className="hero-stats">
            <div className="metric-card">
              <strong>{stats.entities}</strong>
              <span>сутностей</span>
            </div>
            <div className="metric-card">
              <strong>{stats.fields}</strong>
              <span>полів</span>
            </div>
            <div className="metric-card">
              <strong>{stats.relations}</strong>
              <span>зв'язків</span>
            </div>
            <div className="metric-card">
              <strong>{stats.endpoints}</strong>
              <span>AI routes</span>
            </div>
          </div>
        </section>

        <IdeaPanel
          prompt={ideaPrompt}
          loading={loading.draft}
          hasKey={settings.api_key_present || settings.provider === "ollama"}
          activeModel={settings.model}
          onChange={setIdeaPrompt}
          onGenerate={handleGenerateDraft}
          assistantMessage={assistantMessage}
          progressMessages={draftProgress}
          metrics={lastMetrics?.type === "draft" ? lastMetrics : null}
        />

        <section className="panel project-meta-panel">
          <div className="field-row">
            <label className="field-group">
              <span>Назва проєкту</span>
              <input
                value={project.name}
                onChange={(event) => setProjectMeta({ name: event.target.value })}
              />
            </label>
            <label className="field-group">
              <span>База даних</span>
              <select
                value={project.db_type}
                onChange={(event) => setProjectMeta({ db_type: event.target.value })}
              >
                {DB_TYPES.map((dbType) => (
                  <option key={dbType} value={dbType}>
                    {dbType}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-group checkbox-group" style={{ flexDirection: "row", alignItems: "center", gap: "0.5rem", marginTop: "1.5rem" }}>
              <input
                type="checkbox"
                style={{ width: "18px", height: "18px", margin: 0, cursor: "pointer" }}
                checked={project.include_auth}
                onChange={(event) => setProjectMeta({ include_auth: event.target.checked })}
              />
              <span style={{ cursor: "pointer" }}>JWT Auth</span>
            </label>
          </div>

          <label className="field-group">
            <span>Опис</span>
            <textarea
              rows={3}
              value={project.description}
              onChange={(event) => setProjectMeta({ description: event.target.value })}
              placeholder="Коротко опишіть призначення додатку."
            />
          </label>

          <div className="toggle-row">
            <button className="ghost-button" onClick={addEntity}>
              + Додати entity
            </button>
            <button className="primary-button" disabled={loading.save} onClick={handleSaveProject}>
              {loading.save ? "Збереження..." : "Зберегти проєкт"}
            </button>
            <button
              className="accent-button"
              disabled={loading.generate || loading.deploy || loading.endpoints}
              onClick={handleGenerateEndpoints}
              style={{ background: "#10b981" }}
            >
              {loading.endpoints ? `AI працює... (${endpointsSeconds}с)` : "Згенерувати AI ендпоінти"}
            </button>
            <button
              className="accent-button"
              disabled={loading.generate || loading.deploy || loading.endpoints}
              onClick={handleGenerateZip}
            >
              {loading.generate ? "AI працює..." : "Згенерувати ZIP"}
            </button>
            <button
              className="accent-button"
              disabled={loading.generate || loading.deploy || loading.endpoints}
              onClick={handleDeploy}
              style={{ background: "#4f46e5" }}
            >
              {loading.deploy ? "AI працює..." : "Запустити Docker"}
            </button>
          </div>
          {loading.endpoints && (
            <div className="status-banner status-info" style={{ marginTop: "1rem" }}>
              Генерується код для кастомних AI ендпоінтів... Будь ласка, зачекайте.
            </div>
          )}
          {loading.generate && (
            <div className="status-banner status-info" style={{ marginTop: "1rem" }}>
              Генерується код проєкту та створюється ZIP-архів... Будь ласка, зачекайте.
            </div>
          )}
          {loading.deploy && (
            <div className="status-banner status-info" style={{ marginTop: "1rem" }}>
              Розгортання проєкту в Docker-контейнері... Будь ласка, зачекайте.
            </div>
          )}
          {deployUrl && (
            <div className="status-banner status-success" style={{ marginTop: "1rem" }}>
              Бекенд успішно розгорнуто! Відкрийте Swagger: <a href={deployUrl} target="_blank" rel="noreferrer" style={{ color: "#0f766e", fontWeight: "bold", textDecoration: "underline" }}>{deployUrl}</a>
            </div>
          )}
          {lastMetrics?.endpointsTime && (
            <div className="metrics-bar" style={{ marginTop: "1rem", padding: "1rem", background: "#181a19ff", borderRadius: "8px", border: "1px solid #10b981", display: "flex", gap: "2rem", fontSize: "0.9rem" }}>
              <div>Час генерації ендпоінтів: <strong>{lastMetrics.endpointsTime} сек</strong></div>
              <div>Успішно: <strong>{lastMetrics.endpointsSuccess ? "Так" : "Ні"}</strong></div>
              <div>Токени на ендпоінти: <strong>{lastMetrics.endpointsTokens}</strong></div>
            </div>
          )}
          {lastMetrics?.generationTime && (
            <div className="metrics-bar" style={{ marginTop: "1rem", padding: "1rem", background: "#181a19ff", borderRadius: "8px", border: "1px solid #14b8a6", display: "flex", gap: "2rem", fontSize: "0.9rem" }}>
              <div> Час генерації: <strong>{lastMetrics.generationTime} сек</strong></div>
              <div> Статус компіляції (Syntax Check): <strong>{lastMetrics.compileSuccess ? " Успішно" : " Помилка"}</strong></div>
              {lastMetrics.tokensUsed && <div>Токени: <strong>{lastMetrics.tokensUsed}</strong></div>}
            </div>
          )}
        </section>

        <section className="panel">
          <div className="section-header">
            <div>
              <span className="eyebrow">Entities</span>
              <h3>Навігація по моделі</h3>
            </div>
          </div>
          <div className="entity-list">
            {project.entities.map((entity, index) => (
              <div
                key={`${entity.name}-${index}`}
                className={`entity-pill ${selectedEntityIdx === index ? "entity-pill-active" : ""
                  }`}
              >
                <button onClick={() => selectEntity(index)}>{entity.name || `Entity ${index + 1}`}</button>
                <button className="entity-remove" onClick={() => removeEntity(index)}>
                  x
                </button>
              </div>
            ))}
          </div>
        </section>

        <EntityBuilder entityIdx={selectedEntityIdx} entityOptions={entityOptions} />
      </main>

      <aside className="inspector">
        {/* Tab switcher */}
        <div style={{ display: "flex", gap: "0.5rem", padding: "0.5rem 0", marginBottom: "0.5rem" }}>
          <button
            id="tab-workspace-btn"
            className={activeTab === "workspace" ? "primary-button" : "ghost-button"}
            style={{ padding: "0.4rem 0.8rem", borderRadius: "8px", fontSize: "0.8rem" }}
            onClick={() => setActiveTab("workspace")}
          >
            Проєкт
          </button>
          <button
            id="tab-stats-btn"
            className={activeTab === "stats" ? "primary-button" : "ghost-button"}
            style={{ padding: "0.4rem 0.8rem", borderRadius: "8px", fontSize: "0.8rem" }}
            onClick={() => setActiveTab("stats")}
          >
            Статистика
          </button>
        </div>

        {activeTab === "stats" ? (
          <StatsPanel
            lastMetrics={lastMetrics}
            validationReport={validationReport}
          />
        ) : (
          <>
            <ValidationPanel
              report={validationReport}
              loading={loading.validation}
              onIssueClick={handleIssueClick}
            />

            <section className="panel">
              <div className="section-header">
                <div>
                  <span className="eyebrow">Saved Projects</span>
                  <h3>Збережені ZIP-ready проєкти</h3>
                </div>
              </div>
              <div className="project-list">
                {projects.map((savedProject) => (
                  <div
                    key={savedProject.id}
                    className={`project-card ${activeProjectId === savedProject.id ? "project-card-active" : ""
                      }`}
                  >
                    <button
                      className="project-card-main"
                      onClick={() => handleLoadProject(savedProject.id)}
                    >
                      <strong>{savedProject.name}</strong>
                      <span>{savedProject.db_type}</span>
                    </button>
                    <button
                      className="project-card-delete"
                      type="button"
                      onClick={() => handleDeleteProject(savedProject.id)}
                    >
                      x
                    </button>
                  </div>
                ))}
                {projects.length === 0 ? (
                  <div className="empty-inline">Поки немає збережених проєктів.</div>
                ) : null}
              </div>
            </section>

            <section className="panel">
              <div className="section-header">
                <div>
                  <span className="eyebrow">Live Preview</span>
                  <h3>Структура БД</h3>
                </div>
                <div className="toggle-row" style={{ marginTop: 0 }}>
                  <button
                    className={previewMode === "json" ? "primary-button" : "ghost-button"}
                    style={{ padding: "0.4rem 0.8rem", borderRadius: "8px", fontSize: "0.8rem" }}
                    onClick={() => setPreviewMode("json")}
                  >
                    JSON
                  </button>
                  <button
                    className={previewMode === "table" ? "primary-button" : "ghost-button"}
                    style={{ padding: "0.4rem 0.8rem", borderRadius: "8px", fontSize: "0.8rem" }}
                    onClick={() => setPreviewMode("table")}
                  >
                    Таблиці
                  </button>
                  <button
                    className={previewMode === "diagram" ? "primary-button" : "ghost-button"}
                    style={{ padding: "0.4rem 0.8rem", borderRadius: "8px", fontSize: "0.8rem" }}
                    onClick={() => setPreviewMode("diagram")}
                  >
                    Діаграма
                  </button>
                </div>
              </div>
              {previewMode === "json" ? (
                <pre className="dsl-preview">{dslPreview}</pre>
              ) : previewMode === "diagram" ? (
                <ArchitectureDiagram project={deferredProject} />
              ) : (
                <ArchitectureTables project={deferredProject} />
              )}
            </section>
          </>
        )}

        {status ? <div className="status-banner status-info">{status}</div> : null}
      </aside>
    </div>
  );
}
