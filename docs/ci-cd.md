# CI/CD Setup

## Создание self-hosted runner

Создать self-hosted runner для репозитория, следуя официальной инструкции GitHub.

```bash
# Запустить self-hosted runner в фоне
sudo ./svc.sh install
sudo ./svc.sh start
```

## Предварительная настройка секретов окружения
```bash
# Задаем имя целевого окружения (например, staging или production)
ENV_NAME="staging"

# Получаем имя текущего репозитория
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

# Создаем окружение self-hosted и разрешаем деплой только с ветки main
echo '{"deployment_branch_policy":{
  "protected_branches":false,
  "custom_branch_policies":true
}}' | gh api -X PUT "/repos/$REPO/environments/$ENV_NAME" \
  -H "Accept: application/vnd.github+json" \
  --input -

# Разрешаем деплой только с ветки main
echo '{"name":"main","type":"branch"}' | \
  gh api -X POST \
  "/repos/$REPO/environments/$ENV_NAME/deployment-branch-policies" \
  -H "Accept: application/vnd.github+json" \
  --input -

# Логин и пароль от Beget. Обязательно замени your_login и your_password на свои реальные данные!
BEGET_LOGIN="your_login"
BEGET_PASSWORD="your_password"

# Генерируем надежные пароли для проекта и сохраняем их вместе с данными от Beget в секреты GitHub
openssl rand -hex 32 | gh secret set SECRET_KEY --env "$ENV_NAME"
openssl rand -base64 32 | gh secret set POSTGRES_PASSWORD --env "$ENV_NAME"
openssl rand -base64 32 | gh secret set RABBITMQ_PASSWORD --env "$ENV_NAME"
gh secret set BEGET_LOGIN --env "$ENV_NAME" --body "$BEGET_LOGIN"
gh secret set BEGET_PASSWORD --env "$ENV_NAME" --body "$BEGET_PASSWORD"

# Сохраняем обычные настройки проекта (названия, порты, ссылки) в переменные GitHub
gh variable set BACKEND_CORS_ORIGINS --body "http://localhost:3000" --env "$ENV_NAME"
gh variable set COMPOSE_PROJECT_NAME --body "emailalias" --env "$ENV_NAME"
gh variable set PORT --body "8080" --env "$ENV_NAME"
gh variable set POSTGRES_DB --body "emailalias_db" --env "$ENV_NAME"
gh variable set POSTGRES_HOST --body "postgres" --env "$ENV_NAME"
gh variable set POSTGRES_USER --body "postgres" --env "$ENV_NAME"
gh variable set RABBITMQ_HOST --body "rabbitmq" --env "$ENV_NAME"
gh variable set RABBITMQ_USER --body "emailalias" --env "$ENV_NAME"
gh variable set RABBITMQ_VHOST --body "/" --env "$ENV_NAME"
gh variable set REDIS_URL --body "redis://redis:6379/0" --env "$ENV_NAME"
gh variable set SERVICE_DESCRIPTION --body "Service for creating and managing email aliases." --env "$ENV_NAME"
gh variable set SERVICE_NAME --body "EmailAlias Service" --env "$ENV_NAME"
```

## Тестирование полного флоу (CI + CD)

```bash
# Пушим в main → CI → если ок → CD
git commit --allow-empty -m "WIP: full test"
git push -u origin main

# Откатить всё после проверки
git reset --soft HEAD~1
git push --force-with-lease
```
