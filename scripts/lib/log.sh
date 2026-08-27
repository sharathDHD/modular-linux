#!/usr/bin/env bash
# Modular Linux build logging: numbered steps, live percentages,
# PASS/FAIL checkpoints, and a final summary.
#
# Usage:
#   source scripts/lib/log.sh
#   ml_init /path/to/build.log
#   ml_plan_total 6
#   ml_step "Building C prober"; make c && ml_ok || ml_fail
#   ml_checkpoint "name" PASS "detail"
#   ml_summary   # prints table; returns 1 if any FAIL recorded
#
# Env: NO_COLOR=1 disables ANSI colors.

declare -i ML_STEP_I=0 ML_STEP_TOTAL=0
declare -a ML_CHECKPOINTS=()
declare -f -F ML_TTY_DETECTED >/dev/null 2>&1 || ML_TTY=0
ML_TTY=0
[[ -t 1 ]] && ML_TTY=1
[[ "${NO_COLOR:-0}" == "1" ]] && ML_TTY=0
ML_STEP_START=0
ML_STEP_DESC=""
ML_T0=0

_c_green=$'\033[32m'; _c_red=$'\033[31m'; _c_yellow=$'\033[33m'
_c_blue=$'\033[34m'; _c_dim=$'\033[2m'; _c_bold=$'\033[1m'; _c_off=$'\033[0m'
if (( ! ML_TTY )); then
  _c_green=""; _c_red=""; _c_yellow=""; _c_blue=""; _c_dim=""; _c_bold=""; _c_off=""
fi

ml_init() {
  local logfile="$1"
  mkdir -p "$(dirname "$logfile")"
  : > "$logfile"
  ML_T0=${EPOCHREALTIME/./}
  exec > >(tee -a "$logfile") 2>&1
  echo "${_c_bold}== Modular Linux build log ==${_c_off}"
  echo "started: $(date -Is)  log: $logfile"
}

ml_plan_total() { ML_STEP_TOTAL="$1"; }

ml_pct() {  # percent for step i of N
  local i="$1"
  (( ML_STEP_TOTAL > 0 )) || { echo 0; return; }
  echo $(( (i - 1) * 100 / ML_STEP_TOTAL ))
}

ml_now_ms() { echo "${EPOCHREALTIME/./}"; }

ml_step() {
  ML_STEP_DESC="$1"
  ML_STEP_I+=1
  ML_STEP_START=$(ml_now_ms)
  local pct; pct=$(ml_pct "$ML_STEP_I")
  printf '\n%s[%3d%%]%s %s(%d/%d)%s %s %s\n' \
    "$_c_blue" "$pct" "$_c_off" "$_c_dim" "$ML_STEP_I" "$ML_STEP_TOTAL" \
    "$_c_off" "$_c_bold" "$ML_STEP_DESC${_c_off}"
}

ml_dur() {  # seconds.millis between step start and now
  local now diff; now=$(ml_now_ms)
  diff=$(( now - ML_STEP_START ))
  printf '%d.%03ds' "$(( diff / 1000000 ))"     "$(( (diff % 1000000) / 1000 ))"
}

ml_ok()   { printf '  %s✔ OK%s %s\n' "$_c_green" "$_c_off" "${_c_dim}($(ml_dur))${_c_off}"; \
            ml_checkpoint "$ML_STEP_DESC" PASS "${1:-}"; }
ml_fail() { printf '  %s✘ FAIL%s %s\n' "$_c_red" "$_c_off" "${_c_dim}($(ml_dur))${_c_off}"; \
            ml_checkpoint "$ML_STEP_DESC" FAIL "${1:-}"; }
ml_warn() { printf '  %s▲ WARN%s %s\n' "$_c_yellow" "$_c_off" "${_c_dim}($(ml_dur))${_c_off}"; \
            ml_checkpoint "$ML_STEP_DESC" WARN "${1:-}"; }

# Sub-progress inside a long step: ml_sub 45 "Installing packages"
ml_sub() {
  local pct="$1" desc="$2"
  printf '  %s├─%s %3d%% %s\n' "$_c_dim" "$_c_off" "$pct" "$desc"
}

ml_sub_inline() {  # same line updates: ml_sub_inline 45 "text"
  printf '\r  %s├─%s %3d%% %s' "$_c_dim" "$_c_off" "$1" "$2"
  (( ML_TTY )) && return
  printf '\n'
}

ml_checkpoint() {
  local name="$1" status="$2" detail="${3:-}"
  ML_CHECKPOINTS+=("${name}|${status}|${detail}")
  printf '    %s[CHECKPOINT]%s %-9s %s%s%s\n' "$_c_dim" "$_c_off" \
    "$status" "$name" "${detail:+ — }" "$detail"
}

ml_summary() {
  local pass=0 fail=0 warn=0 line name status detail
  local total_secs=$(( ($(ml_now_ms) - ML_T0) / 1000000 ))
  printf '\n%s════════ BUILD SUMMARY ════════%s\n' "$_c_bold" "$_c_off"
  for line in "${ML_CHECKPOINTS[@]}"; do
    IFS='|' read -r name status detail <<<"$line"
    case "$status" in
      PASS) pass=$((pass+1)); printf '  %s✔%s %s\n' "$_c_green" "$_c_off" "$name" ;;
      WARN) warn=$((warn+1)); printf '  %s▲%s %s %s\n' "$_c_yellow" "$_c_off" "$name" "$detail" ;;
      FAIL) fail=$((fail+1)); printf '  %s✘ %s %s%s\n' "$_c_red" "$_c_off" "$name" \
              "${detail:+ — }$detail" ;;
    esac
  done
  printf '\n  checkpoints: %s%d passed%s, %s%d warned%s, %s%d failed%s  |  total: %ds\n' \
    "$_c_green" "$pass" "$_c_off" "$_c_yellow" "$warn" "$_c_off" \
    "$_c_red" "$fail" "$_c_off" "$total_secs"
  (( fail == 0 )) || return 1
  return 0
}
