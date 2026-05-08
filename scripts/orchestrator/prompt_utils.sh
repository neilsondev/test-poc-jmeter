#!/usr/bin/env bash

ask_choice() {
  local prompt="$1"
  local default_value="$2"
  shift 2
  local options=("$@")
  local answer
  while true; do
    echo "$prompt" >&2
    printf "Opcoes: %s\n" "$(join_by ", " "${options[@]}")" >&2
    read -r -p "[default: $default_value] " answer >&2
    answer="${answer:-$default_value}"
    for option in "${options[@]}"; do
      if [[ "$answer" == "$option" ]]; then
        printf "%s" "$answer"
        return 0
      fi
    done
    echo "Valor invalido: $answer" >&2
  done
}

ask_bool() {
  local prompt="$1"
  local default_value="$2"
  local answer
  while true; do
    read -r -p "$prompt [y/n, default: $default_value] " answer >&2
    answer="${answer:-$default_value}"
    case "$answer" in
      y|Y|yes|YES|true|TRUE)
        printf "true"
        return 0
        ;;
      n|N|no|NO|false|FALSE)
        printf "false"
        return 0
        ;;
      *)
        echo "Resposta invalida: $answer" >&2
        ;;
    esac
  done
}

ask_int() {
  local prompt="$1"
  local default_value="$2"
  local answer
  while true; do
    read -r -p "$prompt [default: $default_value] " answer >&2
    answer="${answer:-$default_value}"
    if [[ "$answer" =~ ^[0-9]+$ ]]; then
      printf "%s" "$answer"
      return 0
    fi
    echo "Valor invalido: $answer" >&2
  done
}

confirm_destructive_action() {
  local message="$1"
  local answer
  read -r -p "$message Digite 'sim' para continuar: " answer
  [[ "$answer" == "sim" ]]
}
