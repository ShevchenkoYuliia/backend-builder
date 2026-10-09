export default function AuthScreen({
  mode,
  form,
  loading,
  error,
  onFieldChange,
  onSubmit,
  onSwitchMode,
}) {
  return (
    <main className="auth-screen">
      <section className="auth-hero">
        <span className="eyebrow">Backend Builder Platform</span>
        <h1>Конструктор, який перетворює DSL у готовий FastAPI backend.</h1>
        <p>
          Створюйте сутності, перевіряйте зв'язки, додавайте AI-логіку та одразу
          завантажуйте ZIP з Docker-інфраструктурою.
        </p>

        <div className="hero-grid">
          <article className="hero-card">
            <strong>Візуальний DSL</strong>
            <span>Entities, поля, relations і JSON-специфікація в одному потоці.</span>
          </article>
          <article className="hero-card">
            <strong>Smart validation</strong>
            <span>Попередження про цикли, дублікати та зламану модель ще до export.</span>
          </article>
          <article className="hero-card">
            <strong>Security first</strong>
            <span>Паролі не зберігаються у відкритому вигляді: тільки PBKDF2-SHA256 хеші.</span>
          </article>
          <article className="hero-card">
            <strong>Ready to deploy</strong>
            <span>На виході ви отримуєте структуру FastAPI, Dockerfile та docker-compose.</span>
          </article>
        </div>
      </section>

      <section className="auth-card">
        <div className="section-header">
          <div>
            <span className="eyebrow">Access</span>
            <h2>{mode === "login" ? "Вхід у платформу" : "Створення акаунта"}</h2>
          </div>
          <div className="security-badge">password hashing enabled</div>
        </div>

        <form className="auth-form" onSubmit={onSubmit}>
          {mode === "register" ? (
            <label className="field-group">
              <span>Ім'я</span>
              <input
                value={form.full_name}
                onChange={(event) => onFieldChange("full_name", event.target.value)}
                placeholder="Developer"
              />
            </label>
          ) : null}

          <label className="field-group">
            <span>Email</span>
            <input
              type="email"
              value={form.email}
              onChange={(event) => onFieldChange("email", event.target.value)}
              placeholder="you@example.com"
            />
          </label>

          <label className="field-group">
            <span>Пароль</span>
            <input
              type="password"
              value={form.password}
              onChange={(event) => onFieldChange("password", event.target.value)}
              placeholder="Не менше 8 символів"
            />
          </label>

          <button className="primary-button auth-submit" disabled={loading} type="submit">
            {loading
              ? "Зачекайте..."
              : mode === "login"
                ? "Увійти"
                : "Зареєструватися"}
          </button>
        </form>

        {error ? <div className="status-banner status-error">{error}</div> : null}

        <button className="link-button" onClick={onSwitchMode} type="button">
          {mode === "login"
            ? "Немає акаунта? Створити профіль"
            : "Вже є акаунт? Увійти"}
        </button>
      </section>
    </main>
  );
}
