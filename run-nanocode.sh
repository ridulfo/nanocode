#!/usr/bin/env bash
WORKSPACE=$(realpath "${1:-.}")
PYTHON=$(readlink -f "$(which python)")

exec bwrap \
  --ro-bind /nix/store /nix/store \
  --ro-bind /etc/resolv.conf /etc/resolv.conf \
  --ro-bind /etc/hosts /etc/hosts \
  --ro-bind /etc/ssl /etc/ssl \
  --bind "$WORKSPACE" "$WORKSPACE" \
  --bind /tmp /tmp \
  --proc /proc \
  --dev /dev \
  --tmpfs /run \
  --unshare-pid \
  --unshare-ipc \
  --die-with-parent \
  --chdir "$WORKSPACE" \
  --setenv PATH "$(realpath "$(which coreutils)")/bin:$(realpath "$(which git)")/bin:$(realpath "$(which grep)")/bin:$(realpath "$(which sed)")/bin:$(realpath "$(which find)")/bin" \
  "$PYTHON" -m nanocode "$@"
