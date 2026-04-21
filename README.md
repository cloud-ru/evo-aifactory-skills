# Cloud.ru Skills для AI-агентов

Универсальные скиллы для работы с сервисами [Cloud.ru](https://cloud.ru) из любого AI-агента для разработки.

## Доступные скиллы

| Скилл | Описание |
|-------|----------|
| **cloudru-account-setup** | Создание сервисного аккаунта, API-ключа Foundation Models и IAM access key |
| **cloudru-foundation-models** | Работа с Foundation Models API: список моделей, вызов completions |
| **cloudru-ml-inference** | Деплой и управление ML-моделями на Cloud.ru ML Inference (GPU) |
| **cloudru-vm** | Создание и управление виртуальными машинами Cloud.ru |
| **cloudru-managed-rag** | RAG-пайплайн: базы знаний, семантический поиск, Q&A с LLM |
| **cloudru-ai-agents** | Evolution AI Agents: CRUD агентов/систем/MCP, триггеры, workflows, marketplace, A2A-чат, EvoClaw |

## Быстрый старт

### 1. Настройка креденшалов

Используйте скилл `cloudru-account-setup` (через браузер) или задайте переменные окружения вручную:

```bash
export CP_CONSOLE_KEY_ID="<ваш-key-id>"
export CP_CONSOLE_SECRET="<ваш-secret>"
export PROJECT_ID="<uuid-проекта>"
export CLOUD_RU_FOUNDATION_MODELS_API_KEY="<ваш-fm-api-key>"
```

### 2. Установка зависимостей

```bash
pip install httpx                # все скиллы
pip install boto3                # managed-rag (загрузка в S3)
pip install playwright           # account-setup (логин через браузер)
playwright install chromium      # account-setup (однократно)
```

### 3. Вызов Foundation Model

```bash
python cloudru-foundation-models/scripts/fm.py models
python cloudru-foundation-models/scripts/fm.py call "t-tech/T-lite-it-1.0" --prompt "Привет!"
```

### 4. Деплой модели (ML Inference)

```bash
python cloudru-ml-inference/scripts/ml_inference.py catalog
python cloudru-ml-inference/scripts/ml_inference.py deploy <model_card_id> --name "my-model" --wait
python cloudru-ml-inference/scripts/ml_inference.py call <model_run_id> --prompt "Привет!" --with-auth
```

### 5. Создание виртуальной машины

```bash
python cloudru-vm/scripts/vm.py flavors
python cloudru-vm/scripts/vm.py create \
  --name my-vm --flavor-name lowcost10-2-4 --image-name ubuntu-22.04 \
  --zone-name ru.AZ-1 --disk-size 20 --disk-type-name SSD \
  --login user1 --ssh-key-file ~/.ssh/id_ed25519.pub \
  --wait --floating-ip
```

### 6. RAG-пайплайн

```bash
python cloudru-managed-rag/scripts/managed_rag.py setup \
  --docs-path ./docs --kb-name "my-kb" --bucket-name "my-bucket"
python cloudru-managed-rag/scripts/managed_rag.py search --query "ваш вопрос"
python cloudru-managed-rag/scripts/managed_rag.py ask --query "ваш вопрос"
```

### 7. AI-агенты (Evolution AI Agents)

```bash
python cloudru-ai-agents/scripts/ai_agents.py marketplace list --kind agent
python cloudru-ai-agents/scripts/ai_agents.py agents create \
  --from-marketplace <card_id> --cascade-mcp --name my-agent
python cloudru-ai-agents/scripts/ai_agents.py agents wait <agent_id>
python cloudru-ai-agents/scripts/ai_agents.py chat send <agent_id> --message "Привет!"
```

## Кросс-скилловые сценарии

См. [WORKFLOW.md](WORKFLOW.md) — матрица выбора FM API vs ML Inference и пошаговый гайд: креденшалы → деплой модели → VM → хостинг приложения.

## Использование с AI-агентами

В каждой папке скилла есть файл `SKILL.md` — точка входа для агента. Укажите агенту на нужный `SKILL.md`, и он получит все необходимые инструкции.

Скиллы агент-агностичны — работают с Claude Code, Cursor, Windsurf, Cline, Aider и любым другим агентом, который умеет читать markdown и запускать Python-скрипты.

