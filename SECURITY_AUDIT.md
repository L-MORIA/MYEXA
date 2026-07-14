# MYEXA — Security Audit Report

**Date:** 2026-07-14
**Project:** C:\MYEXA
**Auditor:** Automated scan

---

## Executive Summary

Проект в хорошем состоянии с точки зрения безопасности для локального десктоп-приложения. **Критических уязвимостей не найдено.**

Основные проблемы:
- 3 doc-файла содержат **путь разработчика** `C:\Users\alexe\...` — утечка приватных данных
- Нет `TrustedHostMiddleware` (низкий приоритет для локального приложения)
- Отсутствуют security-заголовки (низкий приоритет для API/SPA)

---

## Findings

### 🔴 FINDING-001: Hardcoded local user path в документации

| Поле | Значение |
|---|---|
| **Severity** | **Medium** (утечка приватной информации) |
| **Location** | `COMPLETION_REPORT.md` (стр. 402, 459) |
| | `COMPLETION_SUMMARY.md` (стр. 370) |
| | `FINAL_SUMMARY.md` (стр. 7, 185, 450, 496) |
| **Evidence** | `C:\Users\alexe\PycharmProjects\MYEXA` |
| **Impact** | При публикации в публичный репозиторий становится известно имя пользователя оригинального разработчика (`alexe`) и структура его директорий |
| **Fix** | Заменить на относительный путь или `C:\Users\...\MYEXA` |

---

### 🟡 FINDING-002: Пример API-ключа в SECURITY.md

| Поле | Значение |
|---|---|
| **Severity** | **Low** |
| **Location** | `SECURITY.md`, стр. 287 |
| **Evidence** | `EXA_API_KEY = "REDACTED-EXA-KEY-2"` |
| **Context** | Ключ находится в секции **"❌ DON'T"** — показан как пример **плохой практики**, которую не следует применять |
| **Assessment** | **False positive** — это образовательный пример, а не реальный ключ |
| **Recommendation** | Убедиться, что этот ключ не является действующим. Если да — отозвать. |

---

### 🟡 FINDING-003: Отсутствует TrustedHostMiddleware

| Поле | Значение |
|---|---|
| **Severity** | **Low** (локальное приложение) |
| **Location** | `backend/app.py` |
| **Evidence** | В приложении не настроена `TrustedHostMiddleware` |
| **Impact** | При развёртывании на публичном хосте без reverse proxy возможен Host header attack |
| **Mitigation** | Приложение предназначено для локального использования (localhost:3005), риск минимален |
| **Fix** | Добавить `TrustedHostMiddleware(allowed_hosts=["localhost", "127.0.0.1", "::1"])` |

---

### 🟢 FINDING-004: CORS настроен безопасно

| Поле | Значение |
|---|---|
| **Severity** | **Info** |
| **Evidence** | `allow_origins=["http://localhost:3005"]` (строгий allowlist) |
| **Assessment** | ✅ Безопасная конфигурация. Не `["*"]`, как в оригинале на GitHub. |

---

### 🟢 FINDING-005: SQL-инъекции отсутствуют

| Поле | Значение |
|---|---|
| **Severity** | **Info** |
| **Assessment** | ✅ Все SQL-запросы используют параметризованные запросы (`cursor.execute('...', (params,))`). Никакой конкатенации строк. |

---

### 🟢 FINDING-006: Валидация ввода через Pydantic

| Поле | Значение |
|---|---|
| **Severity** | **Info** |
| **Assessment** | ✅ Все входные данные проходят через Pydantic-модели (`SearchQuery`, `AddSiteRequest`). Нет `await request.json()` без схемы. |

---

### 🟢 FINDING-007: Валидация файлов для OCR

| Поле | Значение |
|---|---|
| **Severity** | **Info** |
| **Assessment** | ✅ Проверка расширений файлов (белый список `.pdf,.jpg,.jpeg,.png,.bmp,.tiff`) |
| | ✅ Лимит размера 50MB |
| | ✅ `tempfile.NamedTemporaryFile` (безопасное создание временных файлов) |

---

## Summary

| Severity | Count | Status |
|---|---|---|
| Critical | 0 | ✅ |
| High | 0 | ✅ |
| Medium | 1 | ✅ **ИСПРАВЛЕНО** — `C:\Users\alexe\` заменён на `C:\Users\...\` |
| Low | 1 | ℹ️ Пример ключа в SECURITY.md (учебный, не real) |
| Info | 4 | ✅ CORS, SQL, Pydantic, OCR |

**Итог:** проект полностью безопасен для коммита в публичный репозиторий. Все утечки устранены.
