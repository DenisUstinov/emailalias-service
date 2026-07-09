# Онбординг разработчика

## 1. Подготовка окружения

Клонируйте репозиторий и перейдите в папку проекта:

```bash
git clone <repo-url>
cd name-service
```

Скопируйте шаблон переменных окружения:

```bash
cp .env.example .env
```

## 2. Инициализация среды

Установите зависимости и настройте pre-commit хуки (для коммитов и пушей):

```bash
uv sync
uv run pre-commit install -t pre-commit -t pre-push
```

## 3. Запуск базы данных

Поднимите PostgreSQL в Docker:

```bash
make up
```

## 4. Применение миграций

Создайте и примените миграции к базе данных:

```bash
make migrate
```

Если файлов миграций нет в репозитории, вначале создайте миграцию и примените ее:

```bash
make migrate-new
# Message: Initial tables
# Message: Add alias status provisioned
# Message: Add alias status forwarded
# Message: Remove alias status provisioned and forwarded
# Message: Rename alias status deleting to deleted
```

## 5. Инициализация домена по умолчанию

Добавьте домен по умолчанию в базу данных:

```bash
source .env 2>/dev/null
docker compose exec postgres psql -U $POSTGRES_USER \
  -d $POSTGRES_DB \
  -c "INSERT INTO domains (id, fqdn, is_default) \
      VALUES (gen_random_uuid(), 'mcpemail.net', true);"
```

Проверьте, что домен успешно добавлен:

```bash
source .env 2>/dev/null
docker compose exec postgres psql -U $POSTGRES_USER \
  -d $POSTGRES_DB \
  -c "SELECT id, fqdn, is_default FROM domains;"
```
