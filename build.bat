@echo off
python -m PyInstaller --noconfirm --onefile --windowed --name YTDownloader ^
  --collect-all imageio_ffmpeg --collect-all yt_dlp_ejs --collect-submodules yt_dlp ^
  yt_downloader.py
