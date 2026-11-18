# restocrm-ci

Общие проверки процесса RestoCRM для GitHub Actions: второй слой после локальных git-хуков. Reusable workflow `process-checks.yml` вызывают репозитории обоих владельцев (`t88code/*`, `restocrmloyalty/*`).

## Что проверяет

Только на событии `pull_request`:

| Проверка | Правило |
|---|---|
| Заголовок PR: `<тип>(RC-N): …` (типы `feat fix chore docs test refactor perf build ci`, допустимы `!` и несколько номеров `RC-1,RC-2`) | правило 3 |
| В теме каждого коммита PR (без merge-коммитов) есть `RC-N`; исключения: `Revert`, `fixup!`, `squash!`, `amend!` | правило 3 |
| PR не добавляет файлы с секретами и локальной конфигурацией (`.env*`, `appsettings*.json`, `config.ini`, `restocrm.toml`, `license.dat`, `*.pem`, `*.key`, `*.pfx`, `*.p12`, `*.sqlite*`, `*.db`; примеры `*.example`, `*Example*`, `*Template*` разрешены) | правило 6 |
| `gitleaks` по коммитам PR (контейнер `zricethezav/gitleaks`, не `gitleaks-action`: ему нужна лицензия для организаций) | правило 6 |

Логика лежит в `scripts/process-checks.sh` и проверяется локально: `python3 -m unittest tests/test_process_checks.py -v`.

## Как подключить

В `ci.yml` вызывающего репозитория:

```yaml
  process:
    uses: t88code/restocrm-ci/.github/workflows/process-checks.yml@main
```

Права `contents: read` вызывающему репозиторию достаточно. Секреты не нужны.

## Состояние

GitHub Actions сейчас выключены (RC-783), поэтому workflow пока не исполняется; он готов к включению. Когда Actions заработают, сделай проверку `process` обязательной в воротах репозитория.

В отличие от локальных хуков, обойти эту проверку нельзя: `--no-verify` на неё не действует. Исключение — только по прямому слову владельца с записью в PR.

## Откуда правила

Процесс `restocrm-project/process/CLAUDE.md`, строгие правила 3 (RC-N в ветке, заголовке PR и коммитах) и 6 (секреты и локальные файлы не коммитить). Шаблоны имён секретов взяты дословно из хука `process/hooks/pre-commit`; при изменении правил меняй оба места.

## Почему репозиторий публичный

Reusable workflow из приватного репозитория не может вызвать репозиторий другого владельца, а вызывающие живут под двумя владельцами. Секретов и приватных данных здесь нет.
