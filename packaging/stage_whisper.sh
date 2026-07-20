#!/usr/bin/env bash
# Stage a self-contained whisper.cpp CLI into vendor/whisper/ for bundling.
#
# `brew install whisper-cpp` links whisper-cli against Homebrew dylibs (libwhisper
# and the separate ggml formula, referenced by absolute /usr/local paths) that
# won't exist on a user's machine. This copies the binary and its non-system
# dylibs side by side and rewrites every load path to @loader_path, so the CLI
# is relocatable and works even under the frozen app's cleaned environment.
#
# Usage: packaging/stage_whisper.sh [dest_dir]   (default: vendor/whisper)
set -euo pipefail

DEST="${1:-vendor/whisper}"
mkdir -p "$DEST"

BIN="$(brew --prefix whisper-cpp)/bin/whisper-cli"
cp "$BIN" "$DEST/whisper-cli"

# Copy every non-system dylib the binary (transitively) needs, flat into DEST.
copy_deps() {
  local f="$1"
  otool -L "$f" | tail -n +2 | awk '{print $1}' | while read -r dep; do
    case "$dep" in
      /usr/lib/*|/System/*|@loader_path/*) continue ;;
    esac
    local base; base="$(basename "$dep")"
    if [ ! -f "$DEST/$base" ]; then
      # Resolve @rpath/absolute to a real file via Homebrew's lib dirs.
      local src=""
      for d in "$(brew --prefix whisper-cpp)/lib" "$(brew --prefix ggml)/lib"; do
        [ -f "$d/$base" ] && src="$d/$base" && break
      done
      [ -z "$src" ] && [ -f "$dep" ] && src="$dep"
      [ -z "$src" ] && { echo "!! could not resolve $dep" >&2; continue; }
      cp "$src" "$DEST/$base"
      chmod u+w "$DEST/$base"
      copy_deps "$DEST/$base"   # recurse into the copied lib
    fi
  done
}
copy_deps "$DEST/whisper-cli"

# ggml dlopen's its compute backends (CPU variants + BLAS) at runtime from a
# compiled-in Cellar path. Bundle them flat next to the libs so @loader_path
# resolves libggml-base/libomp, and point ggml here via GGML_BACKEND_PATH (set
# by stt.py when it runs the bundled binary).
for so in "$(brew --prefix ggml)"/libexec/*.so; do
  [ -f "$so" ] || continue
  cp "$so" "$DEST/$(basename "$so")"
  chmod u+w "$DEST/$(basename "$so")"
  copy_deps "$DEST/$(basename "$so")"
done

# Rewrite all non-system load paths to @loader_path and re-sign (ad-hoc).
for f in "$DEST"/whisper-cli "$DEST"/*.dylib "$DEST"/*.so; do
  [ -f "$f" ] || continue
  chmod u+w "$f"
  install_name_tool -add_rpath @loader_path "$f" 2>/dev/null || true
  case "$f" in *.dylib|*.so) install_name_tool -id "@loader_path/$(basename "$f")" "$f" ;; esac
  otool -L "$f" | tail -n +2 | awk '{print $1}' | while read -r dep; do
    case "$dep" in
      /usr/lib/*|/System/*|@loader_path/*) continue ;;
    esac
    install_name_tool -change "$dep" "@loader_path/$(basename "$dep")" "$f" 2>/dev/null || true
  done
  codesign --force --sign - "$f" 2>/dev/null || true
done

echo "Staged whisper.cpp into $DEST:"
ls -la "$DEST"
