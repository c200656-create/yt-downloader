#!/usr/bin/env bash
# Сборка для Linux (один исполняемый файл) и macOS (YTDownloader.app)
set -euo pipefail
cd "$(dirname "$0")"

common=(--noconfirm --windowed --name YTDownloader
        --collect-all imageio_ffmpeg --collect-all yt_dlp_ejs --collect-submodules yt_dlp)

if [[ "$(uname)" == "Darwin" ]]; then
  python -m PyInstaller "${common[@]}" --onedir --osx-bundle-identifier io.github.ytdownloader yt_downloader.py
else
  python -m PyInstaller "${common[@]}" --onefile yt_downloader.py
fi
