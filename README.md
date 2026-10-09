# Backend Builder - Low-Code Backend Generator

> Платформа для автоматичної генерації готового FastAPI-бекенду за допомогою візуального редактора та AI-асистента.

---

## Про проєкт

**Backend Builder** - це low-code PaaS-платформа, що дозволяє розробникам та студентам швидко генерувати повноцінний Python/FastAPI бекенд, описуючи структуру даних у вигляді сутностей та зв'язків між ними. Система підтримує AI-асистента для автоматичного складання схем проєкту та генерації нестандартних ендпоінтів.

### Ключові можливості

-  **Візуальний Entity Builder** - створення моделей даних з полями, типами та зв'язками
-  **AI-асистент** - генерація схем проєкту за текстовим описом (підтримка OpenAI, Gemini, Claude, Ollama)
-  **Кодогенерація** - автоматичне створення повноцінного FastAPI-проєкту з моделями, схемами, роутерами, тестами та Docker-конфігурацією
-  **Мультибазовість** - підтримка PostgreSQL, MySQL та MongoDB
-  **JWT-автентифікація** - опціональне підключення модуля авторизації до проєкту
-  **Валідація схем** - перевірка коректності структури перед генерацією
-  **Архітектурна діаграма** - візуалізація сутностей та зв'язків через React Flow
-  **Історія чатів** - збереження та перегляд попередніх запитів до AI

---

## Архітектура

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Nginx      │────▶│   Frontend   │     │   Backend   │
│  (port 80)  │     │  React+Vite  │────▶│   FastAPI   │
└─────────────┘     │  (port 5173) │     │ (port 8000) │
                    └──────────────┘     └──────┬──────┘
                                                │
                                         ┌──────▼──────┐
                                         │   MongoDB   │
                                         │ (port 27017)│
                                         └─────────────┘
```

| Сервіс    | Технологія          | Порт  |
|-----------|---------------------|-------|
| Frontend  | React 18 + Vite     | 5173  |
| Backend   | FastAPI + Uvicorn   | 8000  |
| Database  | MongoDB 7           | 27017 |
| Proxy     | Nginx               | 80    |

---

## Технологічний стек

### Backend
| Бібліотека          | Призначення                        |
|---------------------|------------------------------------|
| FastAPI ≥ 0.110     | REST API фреймворк                 |
| Uvicorn             | ASGI-сервер                        |
| Pydantic v2         | Валідація даних і схеми            |
| Motor ≥ 3.4         | Async MongoDB драйвер              |
| Jinja2              | Шаблонізатор для кодогенерації     |
| anthropic ≥ 0.25    | Claude AI SDK                      |
| PyJWT               | JWT токени                         |
| cryptography        | Хешування паролів                  |
| Black               | Форматування згенерованого коду    |

### Frontend
| Бібліотека    | Призначення                     |
|---------------|---------------------------------|
| React 18      | UI-фреймворк                    |
| Vite 5        | Збірник та dev-сервер           |
| Zustand       | Управління станом               |
| React Flow    | Візуалізація архітектурних схем |
| Axios         | HTTP-клієнт                     |
| Dagre         | Авто-розміщення графів          |

---

## Структура проєкту

```
Shevchenko_Diplom_Project/
├── backend/
│   ├── routes/               # API маршрути
│   │   ├── auth.py           # Реєстрація / логін / профіль
│   │   ├── ai_settings.py    # Налаштування AI-провайдера
│   │   ├── assistant.py      # AI-асистент (чат)
│   │   ├── projects.py       # CRUD проєктів
│   │   ├── validate.py       # Валідація схеми
│   │   └── generate.py       # Генерація коду (ZIP)
│   ├── services/
│   │   ├── generator.py      # Jinja2-кодогенератор
│   │   ├── llm_service.py    # Клієнт LLM-провайдерів
│   │   ├── assistant_service.py  # Логіка чат-асистента
│   │   └── validator.py      # Валідатор ProjectSchema
│   ├── templates/            # Jinja2-шаблони згенерованих файлів
│   ├── tests/                # Pytest тести
│   ├── main.py               # Точка входу FastAPI
│   ├── schemas.py            # Pydantic моделі
│   ├── database.py           # MongoDB підключення
│   ├── security.py           # JWT утиліти
│   ├── dependencies.py       # FastAPI залежності
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── components/       # React компоненти
│       │   ├── AuthScreen.jsx
│       │   ├── EntityBuilder.jsx
│       │   ├── IdeaPanel.jsx
│       │   ├── ArchitectureDiagram.jsx
│       │   ├── ValidationPanel.jsx
│       │   ├── AISettingsPanel.jsx
│       │   ├── ChatHistoryPanel.jsx
│       │   └── StatsPanel.jsx
│       ├── api/client.js     # Axios API-клієнт
│       ├── store/projectStore.js  # Zustand store
│       └── App.jsx
├── nginx/
│   └── nginx.conf            # Reverse proxy конфігурація
└── docker-compose.yml
```

---

##  Швидкий старт

### Передумови

- [Docker](https://www.docker.com/) та Docker Compose
- (Опціонально) [Ollama](https://ollama.ai/) для локального AI

### 1. Клонування репозиторію

```bash
git clone <url-репозиторію>
cd backend-builder
```

### 2. Запуск через Docker Compose

```bash
docker compose up --build
```

| URL                          | Опис                    |
|------------------------------|-------------------------|
| http://localhost             | Веб-інтерфейс (Nginx)   |
| http://localhost:5173        | Frontend (Vite dev)     |
| http://localhost:8000        | Backend API             |
| http://localhost:8000/docs   | Swagger UI              |
| http://localhost:8000/health | Healthcheck             |

### 3. Локальна розробка без Docker

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## Налаштування AI-провайдера

Увійдіть в систему → перейдіть в **AI Settings** → оберіть провайдера:

| Провайдер | Модель за замовч.  | Потрібен API ключ |
|-----------|--------------------|-------------------|
| OpenAI    | gpt-4o-mini        | ✅                |
| Gemini    | gemini-2.0-flash   | ✅                |
| Claude    | claude-3-5-haiku   | ✅                |
| Ollama    | llama3.1           | ❌ (локальний)    |
| Custom    | Будь-яка           | Опціонально       |

Також можна задати ключі через змінні середовища:

```env
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Що генерується

Після натискання **Generate** система створює ZIP-архів з повноцінним FastAPI-проєктом:

```
generated_project/
├── app/
│   ├── main.py            # FastAPI додаток
│   ├── database.py        # Підключення до БД
│   ├── security.py        # JWT (якщо включено auth)
│   ├── models/            # ORM/ODM моделі
│   ├── schemas/           # Pydantic схеми
│   └── routers/           # REST роутери з CRUD
├── tests/
│   └── test_main.py       # Pytest тести
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Тести

```bash
cd backend
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

---

## API Ендпоінти

| Метод  | URL                      | Опис                              |
|--------|--------------------------|-----------------------------------|
| POST   | `/api/auth/register`     | Реєстрація нового користувача     |
| POST   | `/api/auth/login`        | Логін, отримання JWT-токена       |
| GET    | `/api/auth/me`           | Профіль поточного користувача     |
| GET    | `/api/ai-settings`       | Поточні налаштування AI           |
| PUT    | `/api/ai-settings`       | Оновлення AI-провайдера           |
| POST   | `/api/assistant/draft`   | Запит до AI-асистента             |
| GET    | `/api/assistant/history` | Список чатів                      |
| GET    | `/api/projects`          | Список проєктів користувача       |
| POST   | `/api/projects`          | Створення проєкту                 |
| PUT    | `/api/projects/{id}`     | Оновлення проєкту                 |
| DELETE | `/api/projects/{id}`     | Видалення проєкту                 |
| POST   | `/api/validate`          | Валідація схеми проєкту           |
| POST   | `/api/generate`          | Генерація ZIP-архіву коду         |
| GET    | `/health`                | Healthcheck                       |

---

