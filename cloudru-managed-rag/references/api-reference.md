# Cloud.ru Managed RAG — API Reference

## 2. Архитектура API

### Два раздельных API

#### API 1: Managed RAG Public API (v1) -- Management
- **Base URL:** `https://managed-rag.api.cloud.ru`
- **Версия:** 1.0
- **OpenAPI spec:** `https://cloud.ru/docs/api/cdn/rag/ug/_specs/public-api.yaml`
- **Назначение:** CRUD-операции над базами знаний и их версиями
- **Теги:** `KnowledgeBase`, `KnowledgeBaseVersionService`

#### API 2: Managed RAG Search API (v2) -- Search & Generation
- **Base URL:** `https://<knowledge_base_public_url>.managed-rag.inference.cloud.ru`
- **Версия:** 2.0
- **OpenAPI spec:** `https://cloud.ru/docs/api/cdn/rag/ug/_specs/openapi-v3.yaml`
- **Назначение:** поиск по документам и генерация ответов
- **Теги:** `search`, `generation`

**ВАЖНО:** Search API привязан к конкретной базе знаний. Публичный URL базы знаний уникален и задается при создании.

---

## 3. Аутентификация

### Получение ключей доступа
1. Перейти в личный кабинет `https://console.cloud.ru/`
2. Иконка пользователя -> "Ключи доступа"
3. "Создать ключ" -> описание, время жизни (до 365 дней)
4. Система генерирует **Key ID** (логин) и **Key Secret** (пароль)
5. **Key Secret показывается ОДИН раз** -- сохранить немедленно!

### Получение IAM-токена

```
POST https://iam.api.cloud.ru/api/v1/auth/token
Content-Type: application/json

{
  "keyId": "<Key_ID>",
  "secret": "<Key_Secret>"
}
```

Ответ содержит `access_token`.

### Использование токена
Все запросы требуют заголовок:
```
Authorization: Bearer <access_token>
```

### Ограничения
- **TTL токена: 1 час** (не настраивается)
- Один эндпоинт IAM для всех платформ (Windows, macOS, Linux)

---

## 4. API 1: Managed RAG Public API (v1) -- Полный список эндпоинтов

### 4.1 KnowledgeBase_List
**Возвращает список баз знаний**

```
GET /v1/knowledge-bases
```

**Query Parameters:**

| Параметр | Тип | Описание |
|---|---|---|
| `project_id` | string | Идентификатор проекта |
| `page_size` | integer (int32) | Кол-во записей. По умолчанию 50, макс 100 |
| `page_token` | string | Токен следующей страницы (пагинация) |
| `order_by.field` | string | Поле сортировки. Default: `KNOWLEDGEBASE_ORDER_BY_CREATED_AT`. Enum: `KNOWLEDGEBASE_ORDER_BY_CREATED_AT`, `KNOWLEDGEBASE_ORDER_BY_NAME`, `KNOWLEDGEBASE_ORDER_BY_STATUS`, `KNOWLEDGEBASE_ORDER_BY_UPDATED_AT` |
| `order_by.direction` | string | Направление. Default: `KNOWLEDGEBASE_ORDER_BY_ASC`. Enum: `KNOWLEDGEBASE_ORDER_BY_ASC`, `KNOWLEDGEBASE_ORDER_BY_DESC` |
| `filter` | string | Фильтрующее выражение |

**Response 200:** `v1ListKnowledgeBaseResponse`
```json
{
  "data": [<v1KnowledgeBaseResponse>...],
  "next_page_token": "string"
}
```

---

### 4.2 KnowledgeBase_Get
**Возвращает информацию о базе знаний**

```
GET /v1/knowledge-bases/{knowledgebase_id}
```

**Path Parameters:**
- `knowledgebase_id` (required, string) -- ID базы знаний

**Query Parameters:**
- `project_id` (string) -- ID проекта

**Response 200:** `v1KnowledgeBaseResponse`
```json
{
  "knowledgebase_id": "string",
  "project_id": "string",
  "name": "string",
  "namespace": "string",
  "knowledge_base_configuration": {},
  "status": "KNOWLEDGEBASE_PLANNING",
  "searchApiResponse": {
    "url": "string",
    "state": "SEARCH_API_RESPONSE_STATE_PENDING"
  },
  "created_at": "2019-08-24T14:15:22Z",
  "updated_at": "2019-08-24T14:15:22Z",
  "created_by": "string",
  "updated_by": "string",
  "embedder": {
    "name": "string",
    "type": "string",
    "model_id": "string"
  },
  "description": "string"
}
```

---

### 4.3 KnowledgeBase_Delete
**Удаляет базу знаний**

```
DELETE /v1/knowledge-bases/{knowledgebase_id}
```

**Path Parameters:**
- `knowledgebase_id` (required, string) -- ID базы знаний

**Request Body (application/json):**
```json
{
  "project_id": "string"
}
```

**Response 200:** `v1KnowledgeBaseResponse` (данные удаленной БЗ)

---

### 4.4 KnowledgeBaseVersionService_List
**Возвращает список версий базы знаний**

```
GET /v1/knowledge-bases/versions
```

**Query Parameters:**

| Параметр | Тип | Описание |
|---|---|---|
| `project_id` | string | ID проекта |
| `knowledgebase_id` | string | ID базы знаний |
| `page_size` | integer (int32) | Кол-во записей. По умолчанию 50, макс 100 |
| `page_token` | string | Токен следующей страницы |
| `order_by.field` | string | Default: `KNOWLEDGEBASE_VERSION_ORDER_BY_CREATED_AT`. Enum: `KNOWLEDGEBASE_VERSION_ORDER_BY_CREATED_AT`, `KNOWLEDGEBASE_VERSION_ORDER_BY_UUID`, `KNOWLEDGEBASE_VERSION_ORDER_BY_STATUS`, `KNOWLEDGEBASE_VERSION_ORDER_BY_UPDATED_AT` |
| `order_by.direction` | string | Default: `KNOWLEDGEBASE_VERSION_ORDER_BY_ASC`. Enum: `KNOWLEDGEBASE_VERSION_ORDER_BY_ASC`, `KNOWLEDGEBASE_VERSION_ORDER_BY_DESC` |
| `filter` | string | Фильтрующее выражение |

**Response 200:** `v1ListKnowledgeBaseVersionResponse`
```json
{
  "data": [<v1KnowledgeBaseVersionResponse>...],
  "next_page_token": "string"
}
```

---

### 4.5 KnowledgeBaseVersionService_Get
**Возвращает информацию о версии базы знаний**

```
GET /v1/knowledge-bases/versions/{knowledgebase_version_id}
```

**Path Parameters:**
- `knowledgebase_version_id` (required, string) -- ID версии

**Query Parameters:**
- `project_id` (string) -- ID проекта

**Response 200:** `v1KnowledgeBaseVersionResponse`
```json
{
  "knowledgebase_version_id": "string",
  "knowledgebase_id": "string",
  "project_id": "string",
  "description": "string",
  "version": "string",
  "status": "KNOWLEDGEBASE_VERSION_PENDING",
  "knowledge_base_version_settings": {},
  "scheduled_at": "2019-08-24T14:15:22Z",
  "started_at": "2019-08-24T14:15:22Z",
  "finished_at": "2019-08-24T14:15:22Z",
  "created_at": "2019-08-24T14:15:22Z",
  "updated_at": "2019-08-24T14:15:22Z",
  "created_by": "string",
  "updated_by": "string",
  "embedder": {
    "name": "string",
    "type": "string",
    "model_id": "string"
  }
}
```

---

### 4.6 KnowledgeBaseVersionService_Cancel
**Отменяет создание версии базы знаний**

```
POST /v1/knowledge-bases/versions/{knowledgebase_version_id}
```

**Path Parameters:**
- `knowledgebase_version_id` (required, string) -- ID версии

**Request Body (application/json):**
```json
{
  "project_id": "string"
}
```

**Response 200:** `v1KnowledgeBaseVersionResponse`

---

### 4.7 KnowledgeBaseVersionService_ReindexKnowledgeBaseVersion
**Переиндексирует версию базы знаний**

```
POST /v1/knowledge-bases/versions/{knowledgebase_version_id}/reindex
```

**Path Parameters:**
- `knowledgebase_version_id` (required, string) -- ID версии

**Request Body (application/json):**
```json
{
  "knowledgebaseId": "string",
  "projectId": "string"
}
```

**Response 200:** `v1KnowledgeBaseVersionResponse`

---

## 5. API 2: Managed RAG Search API (v2) -- Полный список эндпоинтов

### Base URL
```
https://<knowledge_base_public_url>.managed-rag.inference.cloud.ru
```

Публичный URL базы знаний доступен в поле `searchApiResponse.url` ответа KnowledgeBase_Get.

---

### 5.1 SearchService_Retrieve
**Выполняет поиск по запросу (только поисковая выдача, без LLM)**

```
POST /api/v2/retrieve
```

**Request Body (application/json):**
```json
{
  "knowledge_base_version": "e96ef0f5-724f-43c5-9046-f0c79348be70",
  "query": "Как работает RAG-система?",
  "retrieval_configuration": {
    "number_of_results": 3,
    "retrieval_type": "SEMANTIC"
  },
  "reranking_configuration": {
    "model_name": "string",
    "model_run_id": "string",
    "model_source": "FOUNDATION_MODELS",
    "number_of_reranked_results": 5
  },
  "request_id": "c2a1b5d2-9f3e-4d6a-8c2e-5f9b6a7c9d01"
}
```

**Response 200:** `v2SearchResponse`
```json
{
  "results": [
    {
      "id": "string",
      "content": "string",
      "metadata": {},
      "created_at": "2023-01-15T12:00:00Z",
      "score": 0.95
    }
  ],
  "llm_answer": "",
  "reasoning_content": "",
  "request_id": "string"
}
```

---

### 5.2 SearchService_RetrieveGenerate
**Генерация ответа на основе поиска (полный RAG-пайплайн)**

```
POST /api/v2/retrieve_generate
```

**Request Body (application/json):**
```json
{
  "knowledge_base_version": "e96ef0f5-724f-43c5-9046-f0c79348be70",
  "query": "Как работает RAG-система?",
  "retrieval_configuration": {
    "number_of_results": 3,
    "retrieval_type": "SEMANTIC"
  },
  "reranking_configuration": {
    "model_name": "string",
    "model_run_id": "string",
    "model_source": "FOUNDATION_MODELS",
    "number_of_reranked_results": 5
  },
  "generationConfiguration": {
    "model_name": "t-tech/T-lite-it-1.0",
    "model_run_id": "string",
    "model_source": "FOUNDATION_MODELS",
    "number_of_chunks_in_context": 3,
    "system_prompt": "Ты помощник, отвечающий на вопросы о RAG.",
    "temperature": 1.0,
    "top_p": 1.0,
    "max_completion_tokens": 100,
    "additional_model_request_fields": {}
  },
  "requestId": "c2a1b5d2-9f3e-4d6a-8c2e-5f9b6a7c9d01"
}
```

**Response 200:** `v2SearchResponse`
```json
{
  "results": [
    {
      "id": "string",
      "content": "Текст найденного чанка...",
      "metadata": {},
      "created_at": "2023-01-15T12:00:00Z",
      "score": 0.95
    }
  ],
  "llm_answer": "RAG (Retrieval-Augmented Generation) система объединяет...",
  "reasoning_content": "string",
  "request_id": "string"
}
```

---

## 6. Схемы данных (Data Models)

### v1KnowledgeBaseResponse
| Поле | Тип | Описание |
|---|---|---|
| `knowledgebase_id` | string | ID базы знаний |
| `project_id` | string | ID проекта |
| `name` | string | Название |
| `namespace` | string | Пространство имен |
| `knowledge_base_configuration` | object | Параметры экстрактора, трансформера, S3, логирования |
| `status` | string (v1KnowledgeBaseStatus) | Статус БЗ |
| `searchApiResponse` | object (v1SearchAPIResponse) | URL и состояние Search API |
| `created_at` | string (date-time) | Дата создания |
| `updated_at` | string (date-time) | Дата изменения |
| `created_by` | string | Автор создания |
| `updated_by` | string | Автор изменения |
| `embedder` | object (v1Embedder) | Параметры эмбеддера |
| `description` | string | Описание |

### v1KnowledgeBaseStatus (enum)
- `KNOWLEDGEBASE_PLANNING`
- `KNOWLEDGEBASE_PENDING`
- `KNOWLEDGEBASE_ACTIVE`
- `KNOWLEDGEBASE_SUSPENDING`
- `KNOWLEDGEBASE_INACTIVE`

### v1KnowledgeBaseVersionResponse
| Поле | Тип | Описание |
|---|---|---|
| `knowledgebase_version_id` | string | ID версии |
| `knowledgebase_id` | string | ID базы знаний |
| `project_id` | string | ID проекта |
| `description` | string | Описание |
| `version` | string | Название версии |
| `status` | string (v1KnowledgeBaseVersionStatus) | Статус версии |
| `knowledge_base_version_settings` | object | Параметры экстрактора, трансформера, S3, логирования |
| `scheduled_at` | string (date-time) | Дата запланированного начала |
| `started_at` | string (date-time) | Дата начала |
| `finished_at` | string (date-time) | Дата завершения |
| `created_at` | string (date-time) | Дата создания |
| `updated_at` | string (date-time) | Дата изменения |
| `created_by` | string | Автор создания |
| `updated_by` | string | Автор изменения |
| `embedder` | object (v1Embedder) | Параметры эмбеддера |

### v1KnowledgeBaseVersionStatus (enum)
- `KNOWLEDGEBASE_VERSION_PENDING`
- `KNOWLEDGEBASE_VERSION_SUCCEEDED`
- `KNOWLEDGEBASE_VERSION_FAILED`
- `KNOWLEDGEBASE_VERSION_UNKNOWN`
- `KNOWLEDGEBASE_VERSION_CANCELLED`
- `KNOWLEDGEBASE_VERSION_SUSPENDING`

### v1SearchAPIResponse
| Поле | Тип | Описание |
|---|---|---|
| `url` | string | Публичный URL Search API |
| `state` | string (v1SearchAPIResponseState) | Состояние Search API |

### v1SearchAPIResponseState (enum)
- `SEARCH_API_RESPONSE_STATE_PENDING`
- `SEARCH_API_RESPONSE_STATE_RUNNING`
- `SEARCH_API_RESPONSE_STATE_ACTIVE`
- `SEARCH_API_RESPONSE_STATE_FAILED`
- `SEARCH_API_RESPONSE_STATE_INACTIVE`
- `SEARCH_API_RESPONSE_STATE_UNKNOWN`

### v1Embedder
| Поле | Тип | Описание |
|---|---|---|
| `name` | string | Название модели-эмбеддера |
| `type` | string | Источник (Foundation Models / ML Inference) |
| `model_id` | string | ID модели |

### v2SearchResult
| Поле | Тип | Описание |
|---|---|---|
| `id` | string | Уникальный ID результата |
| `content` | string | Текстовое содержание чанка |
| `metadata` | object | Метаданные (JSON) |
| `created_at` | string (date-time) | Дата создания |
| `score` | float | Релевантность (0-1), 1 = максимум |

### v2GenerationConfiguration
| Поле | Тип | Описание |
|---|---|---|
| `model_name` | string | Наименование LLM-модели |
| `model_run_id` | string | ID инференса (для ML_INFERENCE) |
| `model_source` | string (v2ModelSource) | `FOUNDATION_MODELS` или `ML_INFERENCE` |
| `number_of_chunks_in_context` | int32 | Кол-во чанков для контекста LLM (top-K). Example: 3 |
| `system_prompt` | string | Системный промпт |
| `temperature` | float | Температура. Example: 1.0 |
| `top_p` | float | Сэмплирование. Example: 1.0 |
| `max_completion_tokens` | int32 | Максимум выходных токенов. Example: 100 |
| `additional_model_request_fields` | object | Дополнительные параметры |

**Примечание:** Доступны все параметры из `v1/chat/completions` Foundation Models API, КРОМЕ: `messages`, `model`, `stream`, `stream_options`, `tools`, `tool_choice`, `parallel_tool_calls`.

### v2RetrievalConfiguration
| Поле | Тип | Описание |
|---|---|---|
| `number_of_results` | int32 | Кол-во чанков в выдаче. Example: 3 |
| `retrieval_type` | string | Тип поиска. Сейчас только `SEMANTIC` |

### v2RerankingConfiguration
| Поле | Тип | Описание |
|---|---|---|
| `model_name` | string | Наименование модели реранкера |
| `model_run_id` | string | ID инференса (для ML_INFERENCE) |
| `model_source` | string (v2ModelSource) | `FOUNDATION_MODELS` или `ML_INFERENCE` |
| `number_of_reranked_results` | int32 | Кол-во результатов после переранжирования. Не > number_of_results. Example: 5 |

### v2ModelSource (enum)
- `FOUNDATION_MODELS` -- сервис Evolution Foundation Models
- `ML_INFERENCE` -- сервис Evolution ML Inference

---

## 7. Параметры Search API запроса -- Подробности

### Общие параметры (обязательные)
| Поле | Тип | Описание |
|---|---|---|
| `knowledge_base_version` | string | ID версии или `latest` (последняя активная) |
| `query` | string | Пользовательский запрос |

### Источники моделей
Для `model_source` в reranking_configuration и generation_configuration:
- `FOUNDATION_MODELS` -- готовые модели Cloud.ru. Указать `model_name`.
- `ML_INFERENCE` -- пользовательские модели. Указать `model_run_id`.

При использовании ML Inference:
- **Runtime:** vLLM (все типы) или SGLang (только LLM)
- **Задача модели:** Embedding (эмбеддер), Score (реранкер), Generate (LLM)

### Получение model_run_id
Из публичного URL инференса: `https://12345c60-xxx-4527-xxxx-f789f789fb11.modelrun.inference.cloud.ru` -> ID = `12345c60-xxx-4527-xxxx-f789f789fb11`

---

## 8. OpenAPI спецификации

### Public API (Management)
```
https://cloud.ru/docs/api/cdn/rag/ug/_specs/public-api.yaml
```

### Search API (Search & Generation)
```
https://cloud.ru/docs/api/cdn/rag/ug/_specs/openapi-v3.yaml
```
