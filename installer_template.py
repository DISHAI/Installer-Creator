# installer_template.py
"""
Шаблон установщика с правами администратора 
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import sys
import zipfile
import tempfile
import shutil
import threading
import base64
import io
import ctypes
import subprocess


# ============================================================
# АВТОЗАПРОС ПРАВ АДМИНИСТРАТОРА
# ============================================================
def is_admin():
    """Проверяем, запущено ли от имени администратора"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin():
    """Перезапуск с правами администратора через UAC"""
    if is_admin():
        return True

    try:
        if getattr(sys, 'frozen', False):
            # Скомпилированный .exe
            executable = sys.executable
            params = ''
        else:
            # .py скрипт
            executable = sys.executable
            params = f'"{os.path.abspath(__file__)}"'

        # ShellExecuteW с "runas" вызывает UAC
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, params, None, 1
        )

        # Если ret > 32, значит успешно запустили новый процесс
        if ret > 32:
            sys.exit(0)
        else:
            return False
    except Exception:
        return False


# ============================================================
# ЗАПРОС ПРАВ ПРИ СТАРТЕ
# ============================================================
if not is_admin():
    run_as_admin()
    sys.exit(0)


# ============================================================
# PLACEHOLDER-ы (заменяются создателем при сборке)
# ============================================================
APP_NAME = "{{APP_NAME}}"
APP_VERSION = "{{APP_VERSION}}"
APP_AUTHOR = "{{APP_AUTHOR}}"
APP_DESCRIPTION = "{{APP_DESCRIPTION}}"
MAIN_EXECUTABLE = "{{MAIN_EXECUTABLE}}"
APP_ICON_B64 = "{{APP_ICON_B64}}"
FILES_ARCHIVE_B64 = "{{FILES_ARCHIVE_B64}}"
INSTALL_SIZE_MB = "{{INSTALL_SIZE_MB}}"


# ============================================================
# СОЗДАНИЕ ЯРЛЫКОВ (несколько методов для надёжности)
# ============================================================
def create_shortcut_com(shortcut_path, target_path, working_dir,
                        description="", icon_path=""):
    """Метод 1: через COM-объект (win32com)"""
    try:
        from win32com.client import Dispatch
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = target_path
        shortcut.WorkingDirectory = working_dir
        shortcut.Description = description
        if icon_path and os.path.isfile(icon_path):
            shortcut.IconLocation = icon_path
        else:
            shortcut.IconLocation = target_path
        shortcut.save()
        return True
    except Exception as e:
        print(f"COM метод не сработал: {e}")
        return False


def create_shortcut_powershell(shortcut_path, target_path, working_dir,
                               description="", icon_path=""):
    """Метод 2: через PowerShell (всегда работает)"""
    try:
        icon = icon_path if icon_path and os.path.isfile(icon_path) \
               else target_path

        ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{target_path}"
$Shortcut.WorkingDirectory = "{working_dir}"
$Shortcut.Description = "{description}"
$Shortcut.IconLocation = "{icon}"
$Shortcut.Save()
'''
        result = subprocess.run(
            ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_script],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print(f"PowerShell метод не сработал: {e}")
        return False


def create_shortcut_vbs(shortcut_path, target_path, working_dir,
                        description="", icon_path=""):
    """Метод 3: через VBScript (запасной)"""
    try:
        icon = icon_path if icon_path and os.path.isfile(icon_path) \
               else target_path

        vbs_content = f'''
Set WshShell = CreateObject("WScript.Shell")
Set Shortcut = WshShell.CreateShortcut("{shortcut_path}")
Shortcut.TargetPath = "{target_path}"
Shortcut.WorkingDirectory = "{working_dir}"
Shortcut.Description = "{description}"
Shortcut.IconLocation = "{icon}"
Shortcut.Save
'''
        vbs_path = os.path.join(tempfile.gettempdir(), "create_shortcut.vbs")
        with open(vbs_path, 'w') as f:
            f.write(vbs_content)

        result = subprocess.run(
            ['cscript', '//nologo', vbs_path],
            capture_output=True, timeout=30
        )
        os.unlink(vbs_path)
        return result.returncode == 0
    except Exception as e:
        print(f"VBS метод не сработал: {e}")
        return False


def create_shortcut_reliable(shortcut_path, target_path, working_dir,
                             description="", icon_path=""):
    """Пробуем все методы по очереди"""
    # Метод 1: COM
    if create_shortcut_com(shortcut_path, target_path, working_dir,
                           description, icon_path):
        return True, "COM"

    # Метод 2: PowerShell
    if create_shortcut_powershell(shortcut_path, target_path, working_dir,
                                  description, icon_path):
        return True, "PowerShell"

    # Метод 3: VBScript
    if create_shortcut_vbs(shortcut_path, target_path, working_dir,
                           description, icon_path):
        return True, "VBScript"

    return False, "Все методы не сработали"


def get_desktop_path():
    """Надёжное получение пути к рабочему столу"""
    # Метод 1: через Shell API
    try:
        import ctypes.wintypes
        CSIDL_DESKTOP = 0x0000
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOP, None, 0, buf)
        if buf.value and os.path.isdir(buf.value):
            return buf.value
    except Exception:
        pass

    # Метод 2: через переменные окружения
    try:
        desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
        if os.path.isdir(desktop):
            return desktop
    except Exception:
        pass

    # Метод 3: через winshell
    try:
        import winshell
        return winshell.desktop()
    except Exception:
        pass

    # Метод 4: через реестр
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        )
        desktop = winreg.QueryValueEx(key, "Desktop")[0]
        winreg.CloseKey(key)
        if os.path.isdir(desktop):
            return desktop
    except Exception:
        pass

    return os.path.join(os.path.expanduser("~"), "Desktop")


def get_start_menu_path():
    """Получение пути к меню Пуск"""
    try:
        import ctypes.wintypes
        CSIDL_PROGRAMS = 0x0002
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PROGRAMS, None, 0, buf)
        if buf.value:
            return buf.value
    except Exception:
        pass

    try:
        return os.path.join(
            os.environ['APPDATA'],
            'Microsoft', 'Windows', 'Start Menu', 'Programs'
        )
    except Exception:
        return ""


class InstallerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ── Настройки окна ──
        self.title(f"Установка {APP_NAME}")
        self.geometry("650x520")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.center_window(650, 520)
        self._set_icon()

        # Переменные
        default_path = os.path.join(
            os.environ.get("PROGRAMFILES", "C:\\Program Files"),
            APP_NAME
        )
        self.install_path = ctk.StringVar(value=default_path)
        self.create_shortcut = ctk.BooleanVar(value=True)
        self.create_start_menu = ctk.BooleanVar(value=True)
        self.current_step = 0

        # Показываем что мы админ
        self.is_admin = is_admin()

        # Создаём страницы
        self.pages = []
        self._build_welcome_page()
        self._build_path_page()
        self._build_options_page()
        self._build_install_page()
        self._build_finish_page()

        self._show_page(0)

    def center_window(self, w, h):
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _set_icon(self):
        try:
            if APP_ICON_B64 and APP_ICON_B64 != "{{APP_ICON_B64}}":
                icon_data = base64.b64decode(APP_ICON_B64)
                tmp = tempfile.NamedTemporaryFile(suffix=".ico", delete=False)
                tmp.write(icon_data)
                tmp.close()
                self.iconbitmap(tmp.name)
                os.unlink(tmp.name)
        except Exception:
            pass

    # ════════════════════════════════════════════════════════
    #  СТРАНИЦА 1: Приветствие
    # ════════════════════════════════════════════════════════
    def _build_welcome_page(self):
        page = ctk.CTkFrame(self, fg_color="transparent")
        self.pages.append(page)

        # Баннер
        banner = ctk.CTkFrame(page, height=100, corner_radius=0,
                              fg_color=("#1a73e8", "#1a56a8"))
        banner.pack(fill="x", pady=(0, 15))
        banner.pack_propagate(False)

        ctk.CTkLabel(
            banner, text=f"🚀 {APP_NAME}",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="white"
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            banner, text=f"Версия {APP_VERSION}",
            font=ctk.CTkFont(size=14),
            text_color="#cce0ff"
        ).pack()

        # Контент
        desc_frame = ctk.CTkFrame(page, fg_color=("gray92", "gray17"),
                                  corner_radius=12)
        desc_frame.pack(fill="both", expand=True, padx=30, pady=(0, 10))

        ctk.CTkLabel(
            desc_frame,
            text="Добро пожаловать в мастер установки!",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(25, 10))

        desc_text = APP_DESCRIPTION if APP_DESCRIPTION != "{{APP_DESCRIPTION}}" \
                    else "Эта программа установит приложение на ваш компьютер."
        ctk.CTkLabel(
            desc_frame, text=desc_text,
            font=ctk.CTkFont(size=13),
            wraplength=500, justify="center"
        ).pack(pady=(0, 10))

        info_text = (
            f"👤 Автор: {APP_AUTHOR}\n"
            f"💾 Размер: ~{INSTALL_SIZE_MB} МБ\n"
            f"📁 Главный файл: {MAIN_EXECUTABLE}"
        )
        ctk.CTkLabel(
            desc_frame, text=info_text,
            font=ctk.CTkFont(size=12),
            justify="left",
            text_color=("gray40", "gray60")
        ).pack(pady=(10, 10))

        # Статус прав
        admin_text = "🛡️ Запущено с правами администратора" if self.is_admin \
                     else "⚠️ Нет прав администратора"
        admin_color = "#28a745" if self.is_admin else "orange"
        ctk.CTkLabel(
            desc_frame, text=admin_text,
            font=ctk.CTkFont(size=11),
            text_color=admin_color
        ).pack(pady=(0, 20))

        # Кнопки
        btn_frame = ctk.CTkFrame(page, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(0, 20))

        ctk.CTkButton(
            btn_frame, text="Отмена", width=120,
            fg_color="gray40", hover_color="gray30",
            command=self._on_cancel
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="Далее →", width=150,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._show_page(1)
        ).pack(side="right")

    # ════════════════════════════════════════════════════════
    #  СТРАНИЦА 2: Выбор пути
    # ════════════════════════════════════════════════════════
    def _build_path_page(self):
        page = ctk.CTkFrame(self, fg_color="transparent")
        self.pages.append(page)

        header = ctk.CTkFrame(page, height=60, corner_radius=0,
                              fg_color=("#1a73e8", "#1a56a8"))
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="📂 Выберите папку установки",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white"
        ).pack(pady=15)

        # Прогресс-шаги
        steps = ctk.CTkFrame(page, fg_color="transparent")
        steps.pack(fill="x", padx=30, pady=15)
        step_names = ["Приветствие", "Путь", "Опции", "Установка"]
        for i, name in enumerate(step_names):
            color = "#1a73e8" if i <= 1 else "gray50"
            ctk.CTkLabel(steps, text=f"● {name}",
                        font=ctk.CTkFont(size=11),
                        text_color=color).pack(side="left", padx=10)

        # Путь
        path_frame = ctk.CTkFrame(page, fg_color=("gray92", "gray17"),
                                  corner_radius=12)
        path_frame.pack(fill="both", expand=True, padx=30, pady=10)

        ctk.CTkLabel(
            path_frame,
            text="Укажите директорию для установки:",
            font=ctk.CTkFont(size=14)
        ).pack(pady=(30, 15), padx=20, anchor="w")

        entry_frame = ctk.CTkFrame(path_frame, fg_color="transparent")
        entry_frame.pack(fill="x", padx=20, pady=(0, 20))

        self.path_entry = ctk.CTkEntry(
            entry_frame, textvariable=self.install_path,
            height=40, font=ctk.CTkFont(size=13)
        )
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkButton(
            entry_frame, text="Обзор...", width=100, height=40,
            command=self._browse_folder
        ).pack(side="right")

        ctk.CTkLabel(
            path_frame,
            text=f"⚠️ Требуется ~{INSTALL_SIZE_MB} МБ свободного места",
            font=ctk.CTkFont(size=11),
            text_color="orange"
        ).pack(pady=(0, 30))

        # Кнопки
        btn_frame = ctk.CTkFrame(page, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(0, 20))

        ctk.CTkButton(
            btn_frame, text="← Назад", width=120,
            fg_color="gray40", hover_color="gray30",
            command=lambda: self._show_page(0)
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="Далее →", width=150,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._show_page(2)
        ).pack(side="right")

    # ════════════════════════════════════════════════════════
    #  СТРАНИЦА 3: Опции
    # ════════════════════════════════════════════════════════
    def _build_options_page(self):
        page = ctk.CTkFrame(self, fg_color="transparent")
        self.pages.append(page)

        header = ctk.CTkFrame(page, height=60, corner_radius=0,
                              fg_color=("#1a73e8", "#1a56a8"))
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="⚙️ Параметры установки",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white"
        ).pack(pady=15)

        options_frame = ctk.CTkFrame(page, fg_color=("gray92", "gray17"),
                                     corner_radius=12)
        options_frame.pack(fill="both", expand=True, padx=30, pady=20)

        ctk.CTkLabel(
            options_frame,
            text="Дополнительные действия:",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(30, 20), padx=20, anchor="w")

        ctk.CTkCheckBox(
            options_frame,
            text="🖥️  Создать ярлык на рабочем столе",
            variable=self.create_shortcut,
            font=ctk.CTkFont(size=14),
            checkbox_height=24, checkbox_width=24
        ).pack(pady=10, padx=40, anchor="w")

        ctk.CTkCheckBox(
            options_frame,
            text="📋  Создать запись в меню «Пуск»",
            variable=self.create_start_menu,
            font=ctk.CTkFont(size=14),
            checkbox_height=24, checkbox_width=24
        ).pack(pady=10, padx=40, anchor="w")

        # Сводка
        summary_frame = ctk.CTkFrame(options_frame,
                                     fg_color=("gray85", "gray25"),
                                     corner_radius=8)
        summary_frame.pack(fill="x", padx=20, pady=(30, 20))

        ctk.CTkLabel(
            summary_frame, text="📋 Сводка:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(pady=(10, 5), padx=15, anchor="w")

        self.summary_label = ctk.CTkLabel(
            summary_frame, text="",
            font=ctk.CTkFont(size=12),
            justify="left",
            text_color=("gray30", "gray70")
        )
        self.summary_label.pack(pady=(0, 15), padx=15, anchor="w")

        # Кнопки
        btn_frame = ctk.CTkFrame(page, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(0, 20))

        ctk.CTkButton(
            btn_frame, text="← Назад", width=120,
            fg_color="gray40", hover_color="gray30",
            command=lambda: self._show_page(1)
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="⚡ Установить", width=180,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#28a745", hover_color="#218838",
            command=self._start_install
        ).pack(side="right")

    # ════════════════════════════════════════════════════════
    #  СТРАНИЦА 4: Процесс установки
    # ════════════════════════════════════════════════════════
    def _build_install_page(self):
        page = ctk.CTkFrame(self, fg_color="transparent")
        self.pages.append(page)

        header = ctk.CTkFrame(page, height=60, corner_radius=0,
                              fg_color=("#1a73e8", "#1a56a8"))
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="📦 Установка...",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white"
        ).pack(pady=15)

        content = ctk.CTkFrame(page, fg_color=("gray92", "gray17"),
                               corner_radius=12)
        content.pack(fill="both", expand=True, padx=30, pady=20)

        self.status_emoji = ctk.CTkLabel(
            content, text="⏳", font=ctk.CTkFont(size=50)
        )
        self.status_emoji.pack(pady=(40, 10))

        self.status_label = ctk.CTkLabel(
            content, text="Подготовка...",
            font=ctk.CTkFont(size=15)
        )
        self.status_label.pack(pady=(0, 20))

        self.progress_bar = ctk.CTkProgressBar(
            content, width=450, height=20,
            corner_radius=10, mode="determinate"
        )
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)

        self.percent_label = ctk.CTkLabel(
            content, text="0%",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#1a73e8"
        )
        self.percent_label.pack(pady=5)

        self.file_label = ctk.CTkLabel(
            content, text="",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        )
        self.file_label.pack(pady=(5, 20))

        # Лог
        self.log_textbox = ctk.CTkTextbox(
            content, height=80, font=ctk.CTkFont(size=10),
            fg_color=("gray80", "gray20")
        )
        self.log_textbox.pack(fill="x", padx=20, pady=(0, 20))

    # ════════════════════════════════════════════════════════
    #  СТРАНИЦА 5: Завершение
    # ════════════════════════════════════════════════════════
    def _build_finish_page(self):
        page = ctk.CTkFrame(self, fg_color="transparent")
        self.pages.append(page)

        header = ctk.CTkFrame(page, height=60, corner_radius=0,
                              fg_color=("#28a745", "#1e7e34"))
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="✅ Установка завершена!",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white"
        ).pack(pady=15)

        content = ctk.CTkFrame(page, fg_color=("gray92", "gray17"),
                               corner_radius=12)
        content.pack(fill="both", expand=True, padx=30, pady=20)

        ctk.CTkLabel(
            content, text="🎉", font=ctk.CTkFont(size=60)
        ).pack(pady=(30, 10))

        ctk.CTkLabel(
            content,
            text=f"{APP_NAME} успешно установлен!",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=5)

        self.finish_info = ctk.CTkLabel(
            content, text="",
            font=ctk.CTkFont(size=12),
            justify="center",
            text_color=("gray40", "gray60")
        )
        self.finish_info.pack(pady=15)

        self.shortcut_status = ctk.CTkLabel(
            content, text="",
            font=ctk.CTkFont(size=11),
            text_color="#28a745"
        )
        self.shortcut_status.pack(pady=5)

        self.launch_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            content,
            text=f"🚀 Запустить {APP_NAME} после закрытия",
            variable=self.launch_var,
            font=ctk.CTkFont(size=14)
        ).pack(pady=10)

        btn_frame = ctk.CTkFrame(page, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(0, 20))

        ctk.CTkButton(
            btn_frame, text="📂 Открыть папку", width=150,
            fg_color="gray40", hover_color="gray30",
            command=self._open_install_folder
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="Готово ✓", width=200, height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#28a745", hover_color="#218838",
            command=self._on_finish
        ).pack(side="right")

    # ════════════════════════════════════════════════════════
    #  ЛОГИКА
    # ════════════════════════════════════════════════════════
    def _show_page(self, index):
        for p in self.pages:
            p.pack_forget()
        self.pages[index].pack(fill="both", expand=True)
        self.current_step = index

        if index == 2:
            self._update_summary()

    def _update_summary(self):
        path = self.install_path.get()
        self.summary_label.configure(
            text=f"Программа: {APP_NAME} v{APP_VERSION}\n"
                 f"Путь: {path}\n"
                 f"Размер: ~{INSTALL_SIZE_MB} МБ"
        )

    def _browse_folder(self):
        folder = filedialog.askdirectory(
            title="Выберите папку для установки",
            initialdir=self.install_path.get()
        )
        if folder:
            self.install_path.set(os.path.join(folder, APP_NAME))

    def _on_cancel(self):
        if messagebox.askyesno("Отмена",
                               "Вы уверены, что хотите отменить установку?"):
            self.destroy()

    def _log(self, text):
        """Добавить запись в лог"""
        self.after(0, lambda: self._log_append(text))

    def _log_append(self, text):
        self.log_textbox.insert("end", text + "\n")
        self.log_textbox.see("end")

    def _update_progress(self, value, status="", filename=""):
        self.progress_bar.set(value)
        self.percent_label.configure(text=f"{int(value * 100)}%")
        if status:
            self.status_label.configure(text=status)
        if filename:
            self.file_label.configure(
                text=f"Файл: {filename[:60]}{'...' if len(filename) > 60 else ''}"
            )

    def _start_install(self):
        self._show_page(3)
        thread = threading.Thread(target=self._install_process, daemon=True)
        thread.start()

    def _install_process(self):
        import time
        shortcut_results = []

        try:
            install_dir = self.install_path.get()

            # ── 1. Создание директории ──
            self.after(0, lambda: self._update_progress(
                0.05, "📁 Создание директории..."))
            self._log(f"Создание папки: {install_dir}")
            os.makedirs(install_dir, exist_ok=True)
            time.sleep(0.3)

            # ── 2. Распаковка файлов ──
            self.after(0, lambda: self._update_progress(
                0.1, "📦 Распаковка файлов..."))
            self._log("Распаковка архива...")

            archive_data = base64.b64decode(FILES_ARCHIVE_B64)
            archive_io = io.BytesIO(archive_data)

            with zipfile.ZipFile(archive_io, 'r') as zf:
                file_list = zf.namelist()
                total = len(file_list)
                self._log(f"Файлов в архиве: {total}")

                for i, file in enumerate(file_list):
                    progress = 0.1 + (0.65 * (i + 1) / total)
                    short_name = os.path.basename(file) or file
                    self.after(0, lambda p=progress, f=short_name:
                              self._update_progress(
                                  p, "📦 Распаковка файлов...", f))
                    zf.extract(file, install_dir)

            self._log("Все файлы распакованы!")

            # Проверяем что главный файл существует
            main_exe_path = os.path.join(install_dir, MAIN_EXECUTABLE)
            if not os.path.isfile(main_exe_path):
                # Ищем в подпапках
                for root, dirs, files in os.walk(install_dir):
                    for f in files:
                        if f == MAIN_EXECUTABLE:
                            main_exe_path = os.path.join(root, f)
                            break

            self._log(f"Главный файл: {main_exe_path}")
            self._log(f"Файл существует: {os.path.isfile(main_exe_path)}")

            # ── 3. Ярлык на рабочем столе ──
            if self.create_shortcut.get():
                self.after(0, lambda: self._update_progress(
                    0.80, "🖥️ Создание ярлыка на рабочем столе..."))
                self._log("Создание ярлыка на рабочем столе...")

                desktop = get_desktop_path()
                self._log(f"Путь к рабочему столу: {desktop}")

                shortcut_path = os.path.join(desktop, f"{APP_NAME}.lnk")
                self._log(f"Путь ярлыка: {shortcut_path}")

                success, method = create_shortcut_reliable(
                    shortcut_path=shortcut_path,
                    target_path=main_exe_path,
                    working_dir=install_dir,
                    description=APP_DESCRIPTION if APP_DESCRIPTION != "{{APP_DESCRIPTION}}" else APP_NAME,
                    icon_path=main_exe_path
                )

                if success:
                    self._log(f"✔ Ярлык создан (метод: {method})")
                    # Проверяем что файл реально создался
                    if os.path.isfile(shortcut_path):
                        self._log(f"✔ Файл ярлыка подтверждён: {shortcut_path}")
                        shortcut_results.append(
                            f"✅ Ярлык на рабочем столе создан ({method})"
                        )
                    else:
                        self._log("⚠ Файл ярлыка не найден после создания!")
                        shortcut_results.append(
                            "⚠️ Ярлык создан, но не подтверждён"
                        )
                else:
                    self._log(f"✘ Не удалось создать ярлык: {method}")
                    shortcut_results.append("❌ Не удалось создать ярлык")

                time.sleep(0.3)

            # ── 4. Меню Пуск ──
            if self.create_start_menu.get():
                self.after(0, lambda: self._update_progress(
                    0.90, "📋 Создание записи в меню Пуск..."))
                self._log("Создание записи в меню Пуск...")

                start_menu = get_start_menu_path()
                if start_menu:
                    app_folder = os.path.join(start_menu, APP_NAME)
                    os.makedirs(app_folder, exist_ok=True)

                    sm_shortcut_path = os.path.join(
                        app_folder, f"{APP_NAME}.lnk"
                    )

                    success, method = create_shortcut_reliable(
                        shortcut_path=sm_shortcut_path,
                        target_path=main_exe_path,
                        working_dir=install_dir,
                        description=APP_DESCRIPTION if APP_DESCRIPTION != "{{APP_DESCRIPTION}}" else APP_NAME,
                        icon_path=main_exe_path
                    )

                    if success:
                        self._log(f"✔ Запись в меню Пуск создана ({method})")
                        shortcut_results.append(
                            f"✅ Запись в меню Пуск ({method})"
                        )
                    else:
                        self._log(f"✘ Меню Пуск: {method}")
                        shortcut_results.append("❌ Меню Пуск не создано")

                time.sleep(0.3)

            # ── 5. Информация об установке ──
            self.after(0, lambda: self._update_progress(
                0.97, "📝 Завершение..."))

            info_path = os.path.join(install_dir, "install_info.txt")
            with open(info_path, "w", encoding="utf-8") as f:
                f.write(f"Application: {APP_NAME}\n")
                f.write(f"Version: {APP_VERSION}\n")
                f.write(f"Author: {APP_AUTHOR}\n")
                f.write(f"Install Path: {install_dir}\n")
                f.write(f"Main Executable: {MAIN_EXECUTABLE}\n")
                f.write(f"Full Path: {main_exe_path}\n")

            self._log("Файл информации создан")

            # ── Готово! ──
            self.after(0, lambda: self._update_progress(1.0, "✅ Готово!"))
            self.after(0, lambda: self.status_emoji.configure(text="✅"))
            self._log("═══ Установка завершена успешно! ═══")

            time.sleep(0.8)

            self.after(0, lambda: self._install_complete(
                install_dir, main_exe_path, shortcut_results
            ))

        except PermissionError as e:
            self._log(f"ОШИБКА ДОСТУПА: {e}")
            self.after(0, lambda: self._install_error(
                f"Нет прав доступа: {e}\n\n"
                "Попробуйте запустить установщик от имени администратора."
            ))
        except Exception as e:
            self._log(f"ОШИБКА: {e}")
            import traceback
            self._log(traceback.format_exc())
            self.after(0, lambda: self._install_error(str(e)))

    def _install_complete(self, install_dir, exe_path, shortcut_results):
        self.finish_info.configure(
            text=f"Установлено в:\n{install_dir}"
        )

        # Показываем результаты ярлыков
        if shortcut_results:
            self.shortcut_status.configure(
                text="\n".join(shortcut_results)
            )

        self._exe_path = exe_path
        self._install_dir = install_dir
        self._show_page(4)

    def _install_error(self, error_msg):
        self.status_emoji.configure(text="❌")
        self.status_label.configure(text="Ошибка установки!")
        self.file_label.configure(text="", text_color="red")
        messagebox.showerror("Ошибка", f"Произошла ошибка:\n{error_msg}")

    def _open_install_folder(self):
        if hasattr(self, '_install_dir'):
            os.startfile(self._install_dir)

    def _on_finish(self):
        if self.launch_var.get() and hasattr(self, '_exe_path'):
            try:
                if os.path.isfile(self._exe_path):
                    os.startfile(self._exe_path)
                else:
                    messagebox.showwarning(
                        "Внимание",
                        f"Файл не найден: {self._exe_path}"
                    )
            except Exception as e:
                messagebox.showerror("Ошибка запуска", str(e))
        self.destroy()


if __name__ == "__main__":
    app = InstallerApp()
    app.mainloop()