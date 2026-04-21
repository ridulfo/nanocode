#!/usr/bin/env bash
WORKSPACE=$(realpath "${1:-.}")
exec @bwrap@ \
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
  --setenv PATH "@coreutils@/bin:@git@/bin:@gnugrep@/bin:@gnused@/bin:@findutils@/bin" \
  @nanocode@ "$@"
