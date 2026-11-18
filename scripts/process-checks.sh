#!/usr/bin/env bash
# Проверки процесса RestoCRM для GitHub Actions (RC-983).
# Подкоманды: pr-title "<заголовок>" | commits <base> <head> | secrets <base> <head>
# Совместим с bash 3.2 (macOS) и Ubuntu. Сообщения — аннотации GitHub (::error::).
set -u

TYPES="feat, fix, chore, docs, test, refactor, perf, build, ci"
TITLE_RE='^(feat|fix|chore|docs|test|refactor|perf|build|ci)(!)?\(RC-[0-9]+(,[[:space:]]?RC-[0-9]+)*\)(!)?: .+'

usage() {
  echo "Использование: $0 pr-title \"<заголовок>\" | commits <base_sha> <head_sha> | secrets <base_sha> <head_sha>" >&2
  exit 2
}

cmd_pr_title() {
  local title="${1-}"
  if [[ "$title" =~ $TITLE_RE ]]; then
    echo "Заголовок PR в порядке: ${title}"
    return 0
  fi
  echo "::error title=Заголовок PR::Заголовок «${title}» не по формату. Нужно: <тип>(RC-N): описание (правило 3 процесса). Типы: ${TYPES}. Примеры: feat(RC-123): ..., fix(RC-1,RC-2): ..., feat!(RC-5): ..."
  return 1
}

cmd_commits() {
  [ $# -eq 2 ] || usage
  local base="$1" head="$2" bad="" sha subject count=0
  while IFS="$(printf '\t')" read -r sha subject; do
    [ -n "$sha" ] || continue
    count=$((count + 1))
    case "$subject" in
      Revert*|fixup!*|squash!*|amend!*) continue ;;
    esac
    if ! printf '%s' "$subject" | grep -Eq 'RC-[0-9]+'; then
      bad="$bad${sha:0:8} $subject
"
    fi
  done < <(git log --no-merges --format='%H%x09%s' "$base..$head")
  if [ -n "$bad" ]; then
    echo "::error title=Коммиты без RC-N::В коммитах нет номера RC-N (правило 3 процесса). Перепиши тему: <тип>(RC-N): описание."
    printf '%s' "$bad" | while IFS= read -r line; do
      [ -n "$line" ] && echo "::error::Нет RC-N: ${line}"
    done
    return 1
  fi
  echo "Коммитов проверено: ${count}, у всех есть RC-N."
  return 0
}

cmd_secrets() {
  [ $# -eq 2 ] || usage
  local base="$1" head="$2" bad="" path name
  while IFS= read -r -d '' path; do
    name="${path##*/}"
    case "$name" in
      .env.example|.env.sample|.env.template) continue ;;
      appsettings.*Example*.json|appsettings.*example*.json|appsettings.*Template*.json) continue ;;
    esac
    case "$name" in
      .env|.env.*|appsettings.json|appsettings.*.json|config.ini|restocrm.toml|license.dat|\
*.pem|*.key|*.pfx|*.p12|*.sqlite|*.sqlite3|*.db)
        bad="$bad$path
" ;;
    esac
  done < <(git diff --name-only --diff-filter=A -z "$base...$head")
  if [ -n "$bad" ]; then
    echo "::error title=Файлы с секретами::PR добавляет файлы с секретами или локальной конфигурацией (правило 6 процесса). Держи их в игнорируемых каталогах."
    printf '%s' "$bad" | while IFS= read -r line; do
      [ -n "$line" ] && echo "::error file=${line}::Нельзя добавлять: ${line}"
    done
    return 1
  fi
  echo "Добавленных файлов с секретами нет."
  return 0
}

[ $# -ge 1 ] || usage
sub="$1"; shift
case "$sub" in
  pr-title) cmd_pr_title "$@" ;;
  commits)  cmd_commits "$@" ;;
  secrets)  cmd_secrets "$@" ;;
  *) usage ;;
esac
