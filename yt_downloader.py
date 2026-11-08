"""YT Downloader — простое GUI для скачивания видео с YouTube на базе yt-dlp.

Возможности: выбор качества (до 4K) с сохранением в MP4 со звуком, только аудио (MP3),
плейлисты, очередь загрузок, субтитры, cookies из браузера/файла.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import imageio_ffmpeg
import yt_dlp

APP_NAME = "YT Downloader"
__version__ = "1.1.0"


def _settings_dir():
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", home)
    elif sys.platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return os.path.join(base, "YTDownloader")


SETTINGS_DIR = _settings_dir()
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

QUALITY_BEST = "Лучшее доступное"
QUALITY_AUDIO = "Только аудио (MP3)"
STANDARD_HEIGHTS = [2160, 1440, 1080, 720, 480, 360]
BROWSERS = ["Нет", "firefox", "chrome", "edge", "opera", "brave", "vivaldi", "chromium"]
if sys.platform == "darwin":
    BROWSERS.insert(2, "safari")
MONO_FONT = {"win32": "Consolas", "darwin": "Menlo"}.get(sys.platform, "DejaVu Sans Mono")


class Cancelled(Exception):
    pass


def ffmpeg_path():
    return imageio_ffmpeg.get_ffmpeg_exe()


def height_label(h):
    names = {2160: "4K", 1440: "2K", 1080: "Full HD", 720: "HD"}
    return f"{h}p ({names[h]})" if h in names else f"{h}p"


def label_to_height(label):
    return int(label.split("p", 1)[0])


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def base_opts(cookies_browser, cookies_file):
    opts = {
        "ffmpeg_location": ffmpeg_path(),
        "js_runtimes": {"deno": {"path": None}, "node": {"path": None}},
        "windowsfilenames": True,
        "noprogress": True,
        "quiet": True,
        "no_warnings": False,
    }
    if cookies_file:
        opts["cookiefile"] = cookies_file
    elif cookies_browser and cookies_browser != "Нет":
        opts["cookiesfrombrowser"] = (cookies_browser,)
    return opts


def build_download_opts(job, cookies_browser, cookies_file):
    opts = base_opts(cookies_browser, cookies_file)
    folder = job["folder"]
    if job["playlist"]:
        tmpl = "%(playlist_title|Плейлист)s/%(playlist_index)03d - %(title)s [%(id)s].%(ext)s"
    else:
        tmpl = "%(title)s [%(id)s].%(ext)s"
    opts["outtmpl"] = os.path.join(folder, tmpl)
    opts["noplaylist"] = not job["playlist"]
    opts["ignoreerrors"] = "only_download" if job["playlist"] else False

    pps = []
    if job["quality"] == QUALITY_AUDIO:
        opts["format"] = "ba/b"
        opts["writethumbnail"] = True
        pps += [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"},
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail"},
        ]
    else:
        if job["quality"] == QUALITY_BEST:
            opts["format"] = "bv*+ba/b"
            opts["format_sort"] = ["res", "fps", "vcodec:h264", "acodec:aac"]
        else:
            h = label_to_height(job["quality"])
            opts["format"] = f"bv*[height<={h}]+ba/b[height<={h}]/bv*+ba/b"
            opts["format_sort"] = [f"res:{h}", "fps", "vcodec:h264", "acodec:aac"]
        opts["merge_output_format"] = "mp4"
        pps.append({"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"})
        if job["subs"]:
            langs = [s.strip() for s in job["sub_langs"].split(",") if s.strip()] or ["ru", "en"]
            opts["writesubtitles"] = True
            opts["writeautomaticsub"] = True
            opts["subtitleslangs"] = langs
            pps += [
                {"key": "FFmpegSubtitlesConvertor", "format": "srt"},
                {"key": "FFmpegEmbedSubtitle", "already_have_subtitle": True},
            ]
        pps.append({"key": "FFmpegMetadata", "add_metadata": True})
    opts["postprocessors"] = pps
    return opts


class GuiLogger:
    def __init__(self, emit):
        self.emit = emit

    def debug(self, msg):
        # yt-dlp шлёт info-сообщения через debug с префиксом "[...]"
        if msg.startswith("[download]") or not msg.startswith("["):
            return
        self.emit(msg)

    def info(self, msg):
        self.emit(msg)

    def warning(self, msg):
        self.emit("Предупреждение: " + msg)

    def error(self, msg):
        self.emit(msg)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("900x640")
        self.minsize(760, 520)

        self.settings = load_settings()
        self.events = queue.Queue()
        self.jobs = {}  # item_id -> job dict
        self.job_order = []
        self.worker = None
        self.cancel_current = threading.Event()
        self.current_item = None
        self.analyzed = None  # (url, info)

        self._build_ui()
        self.after(100, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI ----------
    def _build_ui(self):
        style = ttk.Style(self)
        for theme in ("vista", "aqua", "clam"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break
        pad = {"padx": 8, "pady": 4}

        top = ttk.LabelFrame(self, text="Ссылка")
        top.pack(fill="x", **pad)
        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(top, textvariable=self.url_var)
        url_entry.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        url_entry.bind("<Return>", lambda e: self.analyze())
        url_entry.bind("<Button-3>", self._paste_menu)
        ttk.Button(top, text="Вставить", command=self._paste).grid(row=0, column=1, padx=2)
        self.analyze_btn = ttk.Button(top, text="Анализ", command=self.analyze)
        self.analyze_btn.grid(row=0, column=2, padx=6)
        top.columnconfigure(0, weight=1)
        self.info_var = tk.StringVar(value="Вставьте ссылку на видео или плейлист и нажмите «Анализ».")
        ttk.Label(top, textvariable=self.info_var, foreground="#555").grid(
            row=1, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))

        opts = ttk.LabelFrame(self, text="Параметры")
        opts.pack(fill="x", **pad)

        ttk.Label(opts, text="Качество:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.quality_var = tk.StringVar(value=QUALITY_BEST)
        self.quality_cb = ttk.Combobox(opts, textvariable=self.quality_var, state="readonly", width=24)
        self._set_quality_options(STANDARD_HEIGHTS)
        self.quality_cb.grid(row=0, column=1, sticky="w", padx=4)

        self.playlist_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Скачать весь плейлист", variable=self.playlist_var).grid(
            row=0, column=2, sticky="w", padx=12)

        self.subs_var = tk.BooleanVar(value=self.settings.get("subs", False))
        ttk.Checkbutton(opts, text="Субтитры, языки:", variable=self.subs_var).grid(
            row=1, column=0, sticky="w", padx=6, pady=4)
        self.sub_langs_var = tk.StringVar(value=self.settings.get("sub_langs", "ru,en"))
        ttk.Entry(opts, textvariable=self.sub_langs_var, width=26).grid(row=1, column=1, sticky="w", padx=4)

        ttk.Label(opts, text="Cookies из браузера:").grid(row=1, column=2, sticky="e", padx=(12, 4))
        self.browser_var = tk.StringVar(value=self.settings.get("browser", "Нет"))
        ttk.Combobox(opts, textvariable=self.browser_var, values=BROWSERS, state="readonly",
                     width=10).grid(row=1, column=3, sticky="w")
        self.cookie_file_var = tk.StringVar(value=self.settings.get("cookie_file", ""))
        ttk.Button(opts, text="cookies.txt…", command=self._pick_cookies).grid(row=1, column=4, padx=4)

        ttk.Label(opts, text="Папка:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        default_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        self.folder_var = tk.StringVar(value=self.settings.get("folder", default_dir))
        ttk.Entry(opts, textvariable=self.folder_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=4)
        ttk.Button(opts, text="Обзор…", command=self._pick_folder).grid(row=2, column=4, padx=4)
        opts.columnconfigure(3, weight=1)

        self.cookie_info = ttk.Label(opts, foreground="#555")
        self.cookie_info.grid(row=3, column=0, columnspan=5, sticky="w", padx=6, pady=(0, 4))
        self._update_cookie_info()

        btns = ttk.Frame(self)
        btns.pack(fill="x", **pad)
        ttk.Button(btns, text="⬇ Скачать (в очередь)", command=self.add_to_queue).pack(side="left")
        ttk.Button(btns, text="Отменить текущую", command=self.cancel).pack(side="right")
        ttk.Button(btns, text="Удалить выбранные", command=self.remove_selected).pack(side="right", padx=6)
        ttk.Button(btns, text="Очистить готовые", command=self.clear_done).pack(side="right")
        ttk.Button(btns, text="Открыть папку", command=self.open_folder).pack(side="right", padx=6)

        qf = ttk.LabelFrame(self, text="Очередь")
        qf.pack(fill="both", expand=True, **pad)
        cols = ("title", "quality", "status", "progress")
        self.tree = ttk.Treeview(qf, columns=cols, show="headings", height=8)
        for col, text, width in (("title", "Название", 380), ("quality", "Качество", 130),
                                 ("status", "Статус", 150), ("progress", "Прогресс", 170)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")
        sb = ttk.Scrollbar(qf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        sb.pack(side="right", fill="y", pady=6)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", **pad)
        self.progress = ttk.Progressbar(bottom, maximum=100)
        self.progress.pack(fill="x")
        self.status_var = tk.StringVar(value="Готово")
        ttk.Label(bottom, textvariable=self.status_var).pack(anchor="w", pady=(2, 0))

        lf = ttk.LabelFrame(self, text="Журнал")
        lf.pack(fill="both", **pad)
        self.log = tk.Text(lf, height=7, wrap="word", state="disabled", font=(MONO_FONT, 9))
        self.log.pack(fill="both", expand=True, padx=6, pady=6)

    def _set_quality_options(self, heights):
        values = [QUALITY_BEST] + [height_label(h) for h in heights] + [QUALITY_AUDIO]
        self.quality_cb["values"] = values
        if self.quality_var.get() not in values:
            self.quality_var.set(QUALITY_BEST)

    def _paste(self):
        try:
            self.url_var.set(self.clipboard_get().strip())
        except tk.TclError:
            pass

    def _paste_menu(self, event):
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Вставить", command=self._paste)
        m.tk_popup(event.x_root, event.y_root)

    def _pick_folder(self):
        d = filedialog.askdirectory(initialdir=self.folder_var.get() or None)
        if d:
            self.folder_var.set(d)

    def _pick_cookies(self):
        if self.cookie_file_var.get():
            if messagebox.askyesno(APP_NAME, "Сбросить выбранный файл cookies?"):
                self.cookie_file_var.set("")
                self._update_cookie_info()
                return
        f = filedialog.askopenfilename(title="Файл cookies.txt (формат Netscape)",
                                       filetypes=[("cookies", "*.txt"), ("Все файлы", "*.*")])
        if f:
            self.cookie_file_var.set(f)
        self._update_cookie_info()

    def _update_cookie_info(self):
        f = self.cookie_file_var.get()
        if f:
            self.cookie_info.config(text=f"Используется файл cookies: {f}")
        else:
            self.cookie_info.config(text="Если YouTube пишет «not a bot» — выберите Firefox, "
                                         "где вы вошли в YouTube, или укажите файл cookies.txt.")

    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _cookies(self):
        return self.browser_var.get(), self.cookie_file_var.get()

    # ---------- анализ ----------
    def analyze(self):
        url = self.url_var.get().strip()
        if not url:
            return
        self.analyze_btn.state(["disabled"])
        self.info_var.set("Получаю информацию…")
        browser, cfile = self._cookies()
        threading.Thread(target=self._analyze_worker, args=(url, browser, cfile), daemon=True).start()

    def _analyze_worker(self, url, browser, cfile):
        opts = base_opts(browser, cfile)
        opts["extract_flat"] = "in_playlist"
        opts["noplaylist"] = False
        opts["logger"] = GuiLogger(lambda m: self.events.put(("log", m)))
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            self.events.put(("analyzed", url, info))
        except Exception as e:  # noqa: BLE001
            self.events.put(("analyze_error", str(e)))

    def _on_analyzed(self, url, info):
        self.analyze_btn.state(["!disabled"])
        self.analyzed = (url, info)
        if info.get("_type") == "playlist":
            n = len(info.get("entries") or [])
            self.info_var.set(f"Плейлист: {info.get('title', '')} — {n} видео")
            self.playlist_var.set(True)
            self._set_quality_options(STANDARD_HEIGHTS)
            return
        heights = sorted({f["height"] for f in info.get("formats", [])
                          if f.get("height") and f.get("vcodec") not in (None, "none")}, reverse=True)
        self._set_quality_options(heights or STANDARD_HEIGHTS)
        dur = info.get("duration") or 0
        dur_s = f"{int(dur // 3600)}:{int(dur % 3600 // 60):02d}:{int(dur % 60):02d}" if dur else "?"
        best = f"{heights[0]}p" if heights else "?"
        self.info_var.set(f"{info.get('title', '')} — {info.get('uploader', '')} — {dur_s}, макс. {best}")
        self.playlist_var.set(False)

    # ---------- очередь ----------
    def _make_job(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning(APP_NAME, "Вставьте ссылку.")
            return None
        folder = self.folder_var.get().strip()
        if not folder:
            messagebox.showwarning(APP_NAME, "Укажите папку для сохранения.")
            return None
        title = url
        if self.analyzed and self.analyzed[0] == url:
            title = self.analyzed[1].get("title") or url
        self._persist()
        return {
            "url": url, "title": title, "quality": self.quality_var.get(),
            "playlist": self.playlist_var.get(), "subs": self.subs_var.get(),
            "sub_langs": self.sub_langs_var.get(), "folder": folder, "status": "pending",
        }

    def add_to_queue(self):
        job = self._make_job()
        if not job:
            return
        qlabel = job["quality"] + (" · плейлист" if job["playlist"] else "")
        if job["subs"] and job["quality"] != QUALITY_AUDIO:
            qlabel += " · суб."
        item = self.tree.insert("", "end", values=(job["title"], qlabel, "В очереди", ""))
        self.jobs[item] = job
        self.job_order.append(item)
        self.url_var.set("")
        self.analyzed = None
        self.info_var.set("Добавлено в очередь. Можно вставить следующую ссылку.")
        self._ensure_worker()

    def _ensure_worker(self):
        if self.worker and self.worker.is_alive():
            return
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker.start()

    def _next_job(self):
        for item in self.job_order:
            job = self.jobs.get(item)
            if job and job["status"] == "pending":
                job["status"] = "running"
                return item, dict(job)
        return None, None

    def _worker_loop(self):
        while True:
            item, job = self._next_job()
            if not item:
                self.events.put(("idle",))
                return
            self.current_item = item
            self.cancel_current.clear()
            self.events.put(("job_status", item, "Загрузка…", ""))
            browser, cfile = self._cookies()
            opts = build_download_opts(job, browser, cfile)
            opts["logger"] = GuiLogger(lambda m: self.events.put(("log", m)))
            opts["progress_hooks"] = [lambda d, it=item: self._progress_hook(it, d)]
            opts["postprocessor_hooks"] = [lambda d, it=item: self._pp_hook(it, d)]
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    code = ydl.download([job["url"]])
                if code:
                    self.events.put(("job_done", item, "Есть ошибки", False))
                else:
                    self.events.put(("job_done", item, "Готово ✔", True))
            except Cancelled:
                self.events.put(("job_done", item, "Отменено", False))
            except Exception as e:  # noqa: BLE001
                if self.cancel_current.is_set():
                    self.events.put(("job_done", item, "Отменено", False))
                else:
                    self.events.put(("bot_check", str(e)))
                    self.events.put(("job_done", item, "Ошибка ✖", False))
            self.current_item = None

    def _progress_hook(self, item, d):
        if self.cancel_current.is_set():
            raise Cancelled()
        info = d.get("info_dict") or {}
        prefix = ""
        if info.get("playlist_index") and info.get("n_entries"):
            prefix = f"[{info['playlist_index']}/{info['n_entries']}] "
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            pct = done * 100 / total if total else 0
            speed = d.get("speed") or 0
            eta = d.get("eta")
            text = f"{pct:5.1f}%  {done / 1048576:.1f}/{total / 1048576:.1f} МБ"
            status = f"{prefix}{speed / 1048576:.1f} МБ/с" + (f", осталось {int(eta)} с" if eta else "")
            self.events.put(("progress", item, pct, text, status, info.get("title")))
        elif d["status"] == "finished":
            self.events.put(("progress", item, 100, "100%", prefix + "Файл скачан", info.get("title")))

    def _pp_hook(self, item, d):
        if d["status"] == "started":
            names = {"Merger": "Склейка видео и звука", "FFmpegExtractAudio": "Конвертация в MP3",
                     "FFmpegEmbedSubtitle": "Встраивание субтитров", "EmbedThumbnail": "Обложка",
                     "FFmpegVideoRemuxer": "Упаковка в MP4"}
            self.events.put(("job_status", item, names.get(d.get("postprocessor"), "Обработка…"), None))

    def cancel(self):
        if self.current_item:
            self.cancel_current.set()
            self.status_var.set("Отмена…")

    def remove_selected(self):
        for item in self.tree.selection():
            job = self.jobs.get(item)
            if job and job["status"] == "running":
                continue
            self.jobs.pop(item, None)
            if item in self.job_order:
                self.job_order.remove(item)
            self.tree.delete(item)

    def clear_done(self):
        for item in list(self.job_order):
            if self.jobs[item]["status"] in ("done", "failed"):
                self.jobs.pop(item)
                self.job_order.remove(item)
                self.tree.delete(item)

    def open_folder(self):
        folder = self.folder_var.get()
        if os.path.isdir(folder):
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder])

    # ---------- события ----------
    def _poll_events(self):
        try:
            while True:
                ev = self.events.get_nowait()
                kind = ev[0]
                if kind == "log":
                    self._log(ev[1])
                elif kind == "analyzed":
                    self._on_analyzed(ev[1], ev[2])
                elif kind == "analyze_error":
                    self.analyze_btn.state(["!disabled"])
                    self.info_var.set("Не удалось получить информацию — см. журнал.")
                    self._maybe_explain_bot_check(ev[1])
                elif kind == "progress":
                    _, item, pct, text, status, title = ev
                    if self.tree.exists(item):
                        vals = list(self.tree.item(item, "values"))
                        if title and not self.jobs[item]["playlist"]:
                            vals[0] = title
                        vals[3] = text
                        vals[2] = "Загрузка…"
                        self.tree.item(item, values=vals)
                    self.progress["value"] = pct
                    self.status_var.set(status)
                elif kind == "job_status":
                    _, item, status, prog = ev
                    if self.tree.exists(item):
                        vals = list(self.tree.item(item, "values"))
                        vals[2] = status
                        if prog is not None:
                            vals[3] = prog
                        self.tree.item(item, values=vals)
                    self.status_var.set(status)
                elif kind == "job_done":
                    _, item, status, ok = ev
                    if item in self.jobs:
                        self.jobs[item]["status"] = "done" if ok else "failed"
                    if self.tree.exists(item):
                        vals = list(self.tree.item(item, "values"))
                        vals[2] = status
                        self.tree.item(item, values=vals)
                    self._log(f"{status}: {self.jobs.get(item, {}).get('title', '')}")
                elif kind == "bot_check":
                    self._maybe_explain_bot_check(ev[1])
                elif kind == "idle":
                    self.progress["value"] = 0
                    self.status_var.set("Очередь пуста")
                    # могли добавить задание в момент завершения потока
                    if any(j["status"] == "pending" for j in self.jobs.values()):
                        self._ensure_worker()
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _maybe_explain_bot_check(self, err):
        # само сообщение yt-dlp уже попало в журнал через GuiLogger
        if "not a bot" not in err:
            return
        browser, cfile = self._cookies()
        if cfile or browser != "Нет":
            hint = ("Cookies не помогли.\n\n"
                    "Chrome, Edge и другие браузеры на Chromium шифруют cookies так, что сторонние "
                    "программы не могут их прочитать, даже если браузер закрыт.\n\n"
                    "Решение: поставьте в браузер расширение «Get cookies.txt LOCALLY», откройте "
                    "youtube.com (войдя в аккаунт), нажмите Export и укажите сохранённый файл "
                    "кнопкой «cookies.txt…». Или выберите Firefox, если вы вошли в YouTube там.")
        else:
            hint = ("YouTube требует подтверждения, что вы не бот.\n\n"
                    "В поле «Cookies из браузера» выберите браузер, где вы вошли в YouTube "
                    "(работает с Firefox; из Chrome/Edge cookies обычно не читаются), "
                    "или укажите файл cookies.txt, выгруженный расширением "
                    "«Get cookies.txt LOCALLY», затем повторите.")
        messagebox.showinfo(APP_NAME, hint)

    def _persist(self):
        self.settings.update({
            "folder": self.folder_var.get(), "browser": self.browser_var.get(),
            "cookie_file": self.cookie_file_var.get(), "subs": self.subs_var.get(),
            "sub_langs": self.sub_langs_var.get(),
        })
        save_settings(self.settings)

    def _on_close(self):
        if self.current_item and not messagebox.askyesno(APP_NAME, "Идёт загрузка. Выйти всё равно?"):
            return
        self._persist()
        self.destroy()


def self_check(out_path=None):
    """Проверка сборки без GUI: yt-dlp и встроенный ffmpeg на месте и запускаются."""
    ff = ffmpeg_path()
    ff_ver = subprocess.run([ff, "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    report = f"{APP_NAME} {__version__}\nyt-dlp {yt_dlp.version.__version__}\n{ff_ver}\n"
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
    else:
        print(report, end="")


def main():
    if "--check" in sys.argv:
        i = sys.argv.index("--check")
        self_check(sys.argv[i + 1] if len(sys.argv) > i + 1 else None)
        return
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
    App().mainloop()


if __name__ == "__main__":
    main()
