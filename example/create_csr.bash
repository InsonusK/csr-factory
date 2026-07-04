#!/bin/bash
# Генерация приватных ключей и CSR для серверов из директории pki/servers/.
# Для каждого сервера читает meta.yaml, генерирует ключ по указанному алгоритму,
# сохраняет ключ во временный pki/tmp/private.key для копирования в KeePass,
# после подтверждения пользователя создает CSR в pki/servers/<name>/request.csr.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/functions.bash"

SERVERS_DIR="$PKI_ROOT/servers"
TMP_KEY_DIR="$PKI_ROOT/tmp"
TMP_KEY_FILE="$TMP_KEY_DIR/private.key"

mkdir -p "$TMP_KEY_DIR"

# Гарантируем удаление временного ключа при выходе.
cleanup() {
    if [[ -f "$TMP_KEY_FILE" ]]; then
        rm -f "$TMP_KEY_FILE"
        echo "Временный файл $TMP_KEY_FILE удален." >&2
    fi
}
trap cleanup EXIT INT TERM

if [[ ! -d "$SERVERS_DIR" ]]; then
    echo "Ошибка: директория $SERVERS_DIR не найдена." >&2
    exit 1
fi

# Считываем метаданные серверов через Python (PyYAML).
export SERVERS_DIR
mapfile -t server_lines < <(python3 <<'PY'
import os
import sys
import yaml

servers_dir = os.environ.get('SERVERS_DIR', '')
if not os.path.isdir(servers_dir):
    sys.exit(0)

servers = []
for entry in sorted(os.listdir(servers_dir)):
    server_dir = os.path.join(servers_dir, entry)
    if not os.path.isdir(server_dir):
        continue

    meta_path = os.path.join(server_dir, 'meta.yaml')
    cnf_path = os.path.join(server_dir, 'server.cnf')

    if not os.path.isfile(meta_path):
        print(f"WARN|{entry}|нет meta.yaml", file=sys.stderr)
        continue
    if not os.path.isfile(cnf_path):
        print(f"WARN|{entry}|нет server.cnf", file=sys.stderr)
        continue

    try:
        with open(meta_path, encoding='utf-8') as f:
            meta = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"WARN|{entry}|ошибка чтения meta.yaml: {e}", file=sys.stderr)
        continue

    name = meta.get('name') or entry
    tags = meta.get('tags') or []
    algorithm = meta.get('algorithm', 'rsa 2048')
    servers.append((name, server_dir, algorithm, tags))

for name, server_dir, algorithm, tags in sorted(servers, key=lambda x: x[0]):
    print(f"{name}|{server_dir}|{algorithm}|{','.join(str(t) for t in tags)}")
PY
)

if [[ ${#server_lines[@]} -eq 0 ]]; then
    echo "Ошибка: в $SERVERS_DIR не найдены серверы с meta.yaml и server.cnf." >&2
    exit 1
fi

# Заполняем ассоциативные массивы.
declare -A server_dir
declare -A server_algorithm
declare -A server_tags

for line in "${server_lines[@]}"; do
    IFS='|' read -r name dir algo tags <<< "$line"
    server_dir["$name"]="$dir"
    server_algorithm["$name"]="$algo"
    server_tags["$name"]="$tags"
done

# Собираем уникальные тэги.
declare -A all_tags_map
for name in "${!server_tags[@]}"; do
    IFS=',' read -ra tags <<< "${server_tags[$name]}"
    for tag in "${tags[@]}"; do
        [[ -n "$tag" ]] && all_tags_map["$tag"]=1
    done
done

mapfile -t sorted_tags < <(printf '%s\n' "${!all_tags_map[@]}" | sort)
mapfile -t sorted_servers < <(printf '%s\n' "${!server_dir[@]}" | sort)

# Формируем меню выбора.
echo "=== Создание/обновление CSR ==="
echo ""
echo "  0) Все"
echo "--- по тэгам ---"

declare -A tag_menu
i=1
for tag in "${sorted_tags[@]}"; do
    echo "  $i) $tag"
    tag_menu[$i]="$tag"
    ((i++))
done

echo "--- по серверам ---"

declare -A server_menu
for server in "${sorted_servers[@]}"; do
    echo "  $i) $server"
    server_menu[$i]="$server"
    ((i++))
done

echo -n "Ваш выбор: " >&2
read -r choice >&2

# Определяем выбранные серверы.
declare -A selected
if [[ "$choice" == "0" ]]; then
    for server in "${sorted_servers[@]}"; do
        selected["$server"]=1
    done
elif [[ -n "${tag_menu[$choice]:-}" ]]; then
    tag="${tag_menu[$choice]}"
    for server in "${sorted_servers[@]}"; do
        if [[ ",${server_tags[$server]}," == *",$tag,"* ]]; then
            selected["$server"]=1
        fi
    done
elif [[ -n "${server_menu[$choice]:-}" ]]; then
    selected["${server_menu[$choice]}"]=1
else
    echo "Ошибка: неверный выбор." >&2
    exit 1
fi

if [[ ${#selected[@]} -eq 0 ]]; then
    echo "Не выбрано ни одного сервера." >&2
    exit 1
fi

mapfile -t selected_servers < <(printf '%s\n' "${!selected[@]}" | sort)

# Обрабатываем выбранные серверы.
for server in "${selected_servers[@]}"; do
    dir="${server_dir[$server]}"
    algo="${server_algorithm[$server]}"
    cnf_file="$dir/server.cnf"
    csr_file="$dir/request.csr"

    echo ""
    echo "=== Сервер: $server (алгоритм: $algo) ==="

    if [[ -f "$csr_file" ]]; then
        echo "CSR уже существует: $csr_file"
        read -r -p "Перезаписать? (yes/no): " overwrite
        if [[ "$overwrite" != "yes" ]]; then
            echo "Пропуск $server."
            continue
        fi
    fi

    echo "Генерация приватного ключа..."
    case "$algo" in
        "rsa 2048")
            openssl genrsa -out "$TMP_KEY_FILE" 2048
            ;;
        "rsa 4096")
            openssl genrsa -out "$TMP_KEY_FILE" 4096
            ;;
        "ECC P-256")
            openssl ecparam -genkey -name prime256v1 -out "$TMP_KEY_FILE"
            ;;
        "ECC P-384")
            openssl ecparam -genkey -name secp384r1 -out "$TMP_KEY_FILE"
            ;;
        *)
            echo "Ошибка: неизвестный алгоритм '$algo' для сервера $server." >&2
            exit 1
            ;;
    esac
    chmod 600 "$TMP_KEY_FILE"

    echo "Приватный ключ сохранен в: $TMP_KEY_FILE"
    echo "Скопируйте его в KeePass и нажмите Enter для создания CSR..."
    read -r

    openssl req -new -key "$TMP_KEY_FILE" -out "$csr_file" -config "$cnf_file"
    rm -f "$TMP_KEY_FILE"

    echo "CSR создан: $csr_file"
done

echo ""
echo "=== Готово. ==="
