# Cloud.ru Skills — кросс-скилловые сценарии

## FM API vs ML Inference — что когда использовать

| | Foundation Models API | ML Inference (Model RUN) |
|---|---|---|
| **Модель** | Предустановлена Cloud.ru | Вы деплоите свою |
| **Тарификация** | За токены (некоторые модели бесплатны) | За GPU-час (фиксированная) |
| **Управление GPU** | Не нужно (serverless) | Вы выбираете тип и количество GPU |
| **Латентность** | Выше (shared-инфра) | Ниже (выделенный GPU) |
| **Модели** | Только каталог Cloud.ru | Любая модель с HuggingFace/Ollama |
| **Авторизация** | API-ключ (`CLOUD_RU_FOUNDATION_MODELS_API_KEY`) | IAM-токен или без авторизации (`isEnabledAuth`) |
| **Эндпоинт** | `https://foundation-models.api.cloud.ru/v1` | `https://<id>.modelrun.inference.cloud.ru/v1` |
| **Лучше для** | Быстрые эксперименты, низкий трафик, бесплатные модели | Продакшн, высокий трафик, кастомные/embedding/rerank-модели |

Оба эндпоинта **OpenAI-совместимы** — формат `/v1/chat/completions`. ML Inference также поддерживает `/v1/embeddings` и `/v1/rerank` для embedding- и reranker-моделей.

## Managed RAG — когда использовать

Используйте `cloudru-managed-rag`, когда нужен семантический поиск или Q&A по вашим документам без самостоятельной сборки пайплайна. Managed RAG берёт на себя чанкинг, эмбеддинг, индексацию и поиск — вы просто загружаете документы и делаете запросы.

| | Managed RAG | Вручную (ML Inference embeddings + своя векторная БД) |
|---|---|---|
| **Настройка** | Одна команда (`setup`) | Деплой embedding-модели, настройка векторной БД, код для загрузки |
| **Обработка документов** | Автоматический чанкинг и индексация | Вы управляете чанкингом, эмбеддингами и хранением |
| **Поиск** | Встроенный API семантического поиска | Вы запрашиваете свою векторную БД |
| **Ответы LLM** | Встроенный RAG-пайплайн (`ask`) | Вы оркестрируете retrieval + вызов LLM |
| **Кастомизация** | Ограниченная (размер чанка, реранкер) | Полный контроль |
| **Лучше для** | Быстрое прототипирование, стандартный RAG | Кастомные пайплайны, нестандартный retrieval |

## Почему два механизма авторизации

- **Foundation Models API** использует простой API-ключ (`CLOUD_RU_FOUNDATION_MODELS_API_KEY`), потому что это управляемый serverless-сервис.
- **ML Inference** и **VM** используют IAM-креденшалы (`CP_CONSOLE_KEY_ID` + `CP_CONSOLE_SECRET`), потому что управляют облачными ресурсами (GPU, VM) от вашего имени.
- Оба типа креденшалов создаются скиллом `cloudru-account-setup` за один шаг.

## Сквозной сценарий: от нуля до работающего приложения

### Шаг 1: Создание креденшалов (cloudru-account-setup)

```bash
python3 cloudru-account-setup/scripts/browser_login.py
```

Скрипт создаёт все креденшалы:
- `CLOUD_RU_FOUNDATION_MODELS_API_KEY` — для Foundation Models API
- `CP_CONSOLE_KEY_ID` + `CP_CONSOLE_SECRET` — для ML Inference и VM
- `PROJECT_ID` — UUID вашего проекта

Сохраните их в `.env`:
```bash
cat > .env << 'EOF'
CLOUD_RU_FOUNDATION_MODELS_API_KEY=...
CP_CONSOLE_KEY_ID=...
CP_CONSOLE_SECRET=...
PROJECT_ID=...
EOF
```

### Шаг 2a: Foundation Models (самый быстрый — без деплоя)

```bash
# Список доступных моделей (некоторые бесплатны!)
python3 cloudru-foundation-models/scripts/fm.py models

# Вызов модели
python3 cloudru-foundation-models/scripts/fm.py call openai/gpt-oss-120b --prompt "Привет!"
```

### Шаг 2b: Деплой своей модели (ML Inference)

```bash
# Каталог моделей
python3 cloudru-ml-inference/scripts/ml_inference.py catalog

# Деплой с ожиданием готовности
python3 cloudru-ml-inference/scripts/ml_inference.py deploy <model_card_id> --name my-model --wait

# Вызов (auth включён по умолчанию при деплое)
python3 cloudru-ml-inference/scripts/ml_inference.py call <model_run_id> --prompt "Привет!" --with-auth
```

### Шаг 2c: RAG по вашим документам (Managed RAG)

```bash
# Одна команда: создаёт S3-бакет, загружает документы, создаёт и индексирует базу знаний
python3 cloudru-managed-rag/scripts/managed_rag.py setup \
  --docs-path ./docs --kb-name my-kb --bucket-name my-bucket

# Семантический поиск
python3 cloudru-managed-rag/scripts/managed_rag.py search --query "как работает X?"

# Полный RAG: поиск + ответ LLM
python3 cloudru-managed-rag/scripts/managed_rag.py ask --query "как работает X?"
```

### Шаг 3: Создание VM для хостинга приложения

```bash
# Создание VM с Docker, публичным IP, ожидание SSH
python3 cloudru-vm/scripts/vm.py create \
  --name app-server \
  --login user1 --ssh-key-file ~/.ssh/id_ed25519.pub \
  --cloud-init-file cloudru-vm/assets/cloud-init-docker.yaml \
  --wait --floating-ip --wait-ssh

# Ожидание cloud-init (установка Docker)
python3 cloudru-vm/scripts/vm.py ssh <vm_id> -i ~/.ssh/id_ed25519 -c "cloud-init status --wait"

# Открытие портов
python3 cloudru-vm/scripts/vm.py sg-rule-add <sg_id> --ports 8080
```

### Шаг 4: Деплой приложения на VM

```bash
# Загрузка файлов
python3 cloudru-vm/scripts/vm.py scp <vm_id> -i ~/.ssh/key \
  --local-path ./docker-compose.yml --remote-path /home/user1/docker-compose.yml

# Запуск
python3 cloudru-vm/scripts/vm.py ssh <vm_id> -i ~/.ssh/key \
  -c "cd /home/user1 && docker compose up -d"
```

Ваше приложение может вызывать модели по адресам:
- FM API: `https://foundation-models.api.cloud.ru/v1`
- ML Inference: `https://<model_run_id>.modelrun.inference.cloud.ru/v1`
- Managed RAG: `https://<kb_id>.managed-rag.inference.cloud.ru`
