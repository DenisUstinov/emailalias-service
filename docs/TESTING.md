# Testing

## Предварительная настройка секретов окружения

```bash
# Узнать имя репозитория
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

# Создание/обновление окружения с активацией кастомных политик деплоя
echo '{"deployment_branch_policy":{
  "protected_branches":false,
  "custom_branch_policies":true
}}' | gh api -X PUT "/repos/$REPO/environments/production" \
  -H "Accept: application/vnd.github+json" \
  --input -

# Добавление правила деплоя для тегов, соответствующих маске v*
echo '{"name":"v*","type":"tag"}' | \
  gh api -X POST \
  "/repos/$REPO/environments/production/deployment-branch-policies" \
  -H "Accept: application/vnd.github+json" \
  --input -

# Сгенерировать переменные окружения
openssl rand -hex 32 | \
  gh secret set SECRET_KEY --env production
openssl rand -base64 32 | \
  gh secret set POSTGRES_PASSWORD --env production
openssl rand -base64 32 | \
  gh secret set RABBITMQ_PASSWORD --env production
gh variable set COMPOSE_PROJECT_NAME \
  --body "emailalias" \
  --env production
gh variable set SERVICE_NAME \
  --body "EmailAlias Service" \
  --env production
gh variable set SERVICE_DESCRIPTION \
  --body "Service for creating and managing email aliases." \
  --env production
gh variable set PORT \
  --body "8080" \
  --env production
gh variable set BACKEND_CORS_ORIGINS \
  --body "http://localhost:3000" \
  --env production
gh variable set POSTGRES_DB \
  --body "emailalias_db" \
  --env production
gh variable set POSTGRES_HOST \
  --body "postgres" \
  --env production
gh variable set POSTGRES_USER \
  --body "postgres" \
  --env production
gh variable set REDIS_URL \
  --body "redis://redis:6379/0" \
  --env production
gh variable set RABBITMQ_HOST \
  --body "rabbitmq" \
  --env production
gh variable set RABBITMQ_USER \
  --body "emailalias" \
  --env production
```

## Тестирование полного флоу (CI + CD)

```bash
# Ветка → CI → если ок → тег → Deploy
git checkout -b temp/full-test
git commit --allow-empty -m "WIP: full test"
git push -u origin temp/full-test
git tag v0.0.1-test
git push origin v0.0.1-test

# Откатить всё после проверки
git push origin --delete temp/full-test
git tag -d v0.0.1-test
git push origin --delete v0.0.1-test
git reset --soft HEAD~1
git checkout main
git branch -d temp/full-test
```
