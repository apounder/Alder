#!/usr/bin/env bash
set -euo pipefail
studio_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Local shared libraries are used only in this minimal Linux workspace.
studio_libs="$studio_dir/.runtime/usr/lib/$(uname -m)-linux-gnu"
if [[ -d "$studio_libs" ]]; then
    export LD_LIBRARY_PATH="$studio_libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
if [[ "${1:-}" == "--software" ]]; then
    shift
    export QT_QPA_PLATFORM=xcb
    export LIBGL_ALWAYS_SOFTWARE=1
    export GALLIUM_DRIVER=llvmpipe
    export QT_QUICK_BACKEND=software
    export QTWEBENGINE_CHROMIUM_FLAGS="${QTWEBENGINE_CHROMIUM_FLAGS:-} --use-gl=angle --use-angle=gl --disable-vulkan --ignore-gpu-blocklist --disable-gpu-compositing"
    if [[ -f /usr/share/vulkan/icd.d/lvp_icd.json ]]; then
        export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json
    fi
fi
exec "$studio_dir/.venv/bin/python" "$studio_dir/run_studio.py" "$@"
