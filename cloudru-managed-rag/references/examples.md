# Managed RAG — Примеры использования

## Базовый поиск

```bash
python scripts/managed_rag.py search --query "Как настроить мониторинг?" --limit 5
```

## RAG с кастомной моделью

```bash
python scripts/managed_rag.py ask \
  --query "Опиши процесс деплоя" \
  --model "t-tech/T-lite-it-1.0" \
  --system-prompt "Отвечай кратко, по пунктам" \
  --limit 5
```

## Поиск с reranking

```bash
python scripts/managed_rag.py search \
  --query "требования к безопасности" \
  --rerank-model "BAAI/bge-reranker-v2-m3" \
  --rerank-results 3
```

## Полный setup с нуля

```bash
# 1. Credentials (через cloudru-account-setup)
# 2. Инфраструктура
python scripts/managed_rag.py setup \
  --token "eyJ..." \
  --project-id "..." \
  --customer-id "..." \
  --docs-path ./my-documents \
  --kb-name "project-docs" \
  --bucket-name "my-rag-bucket"

# 3. Поиск
python scripts/managed_rag.py search --query "что нового?"
```

## Управление KB

```bash
# Список
python scripts/managed_rag.py list

# Детали
python scripts/managed_rag.py get --kb-id <ID>

# Версии
python scripts/managed_rag.py versions --kb-id <ID>

# Переиндексация
python scripts/managed_rag.py reindex --version-id <ID>

# Удаление
python scripts/managed_rag.py delete --kb-id <ID>
```
