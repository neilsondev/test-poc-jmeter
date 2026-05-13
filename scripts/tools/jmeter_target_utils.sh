#!/usr/bin/env bash

validate_target() {
  local target="${1:-}"
  case "$target" in
    spring|python|both)
      ;;
    *)
      echo "Target invalido: $target" >&2
      return 1
      ;;
  esac
}

prepare_target_plan() {
  local target="$1"
  local plan_path="$2"
  local run_dir="$3"
  local plan_dir filtered_plan plan_base

  validate_target "$target" || return 1
  mkdir -p "$run_dir"

  if [[ "$target" == "both" ]]; then
    printf "%s" "$plan_path"
    return 0
  fi

  plan_dir="$(dirname "$plan_path")"
  plan_base="$(basename "$plan_path" .jmx)"
  filtered_plan="$plan_dir/.target_${target}_${plan_base}.jmx"

  python3 scripts/tools/filter_jmx_by_target.py \
    --input "$plan_path" \
    --output "$filtered_plan" \
    --target "$target" >/dev/null

  printf "%s" "$filtered_plan"
}
