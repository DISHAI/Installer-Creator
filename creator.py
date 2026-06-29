# creator.py
"""
Консольный создатель установщиков v2.1
С поддержкой UAC и надёжного создания ярлыков
"""

import os
import sys
import zipfile
import base64
import io
import shutil
import subprocess
from pathlib import Path


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   ██╗███╗   ██╗███████╗████████╗ █████╗ ██╗     ██╗      ║
║   ██║████╗  ██║██╔════╝╚══██╔══╝██╔══██╗██║     ██║      ║
║   ██║██╔██╗ ██║███████╗   ██║   ███████║██║     ██║      ║
║   ██║██║╚██╗██║╚════██║   ██║   ██╔══██║██║     ██║      ║
║   ██║██║ ╚████║███████║   ██║   ██║  ██║███████╗███████╗  ║
║   ╚═╝╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚══════╝  ║
║                                                           ║
║      🔨  СОЗДАТЕЛЬ УСТАНОВЩИКОВ  v1.0  🔨                ║
║      🛡️  С правами администратора + ярлыки               ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
{Colors.END}"""
    print(banner)


def print_step(step_num, total, title):
    filled = "█" * step_num
    empty = "░" * (total - step_num)
    print(f"\n{Colors.BLUE}{Colors.BOLD}"
          f"[{filled}{empty}] Шаг {step_num}/{total}: {title}"
          f"{Colors.END}")
    print(f"{Colors.DIM}{'─' * 60}{Colors.END}")


def input_styled(prompt, default=""):
    default_text = f" {Colors.DIM}[{default}]{Colors.END}" if default else ""
    result = input(
        f"  {Colors.YELLOW}▸{Colors.END} {prompt}{default_text}: "
    ).strip()
    return result if result else default


def print_success(msg):
    print(f"  {Colors.GREEN}✔{Colors.END} {msg}")


def print_error(msg):
    print(f"  {Colors.RED}✘{Colors.END} {msg}")


def print_info(msg):
    print(f"  {Colors.CYAN}ℹ{Colors.END} {msg}")


def print_warning(msg):
    print(f"  {Colors.YELLOW}⚠{Colors.END} {msg}")


def get_folder_size(folder):
    total = 0
    for dirpath, _, filenames in os.walk(folder):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return round(total / (1024 * 1024), 1)


def list_files_in_folder(folder):
    files = []
    for dirpath, _, filenames in os.walk(folder):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            rel = os.path.relpath(fp, folder)
            size = os.path.getsize(fp)
            files.append((rel, size))
    return files


def create_archive(source_folder):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED,
                         compresslevel=9) as zf:
        for root, dirs, files in os.walk(source_folder):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_folder)
                zf.write(file_path, arcname)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')


def encode_icon(icon_path):
    if icon_path and os.path.isfile(icon_path):
        with open(icon_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    return ""


def build_installer_script(config):
    template_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "installer_template.py"
    )

    if not os.path.isfile(template_path):
        print_error(f"Шаблон не найден: {template_path}")
        print_info("Убедитесь что installer_template.py рядом с creator.py")
        sys.exit(1)

    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

    replacements = {
        '{{APP_NAME}}': config['app_name'],
        '{{APP_VERSION}}': config['app_version'],
        '{{APP_AUTHOR}}': config['app_author'],
        '{{APP_DESCRIPTION}}': config['app_description'],
        '{{MAIN_EXECUTABLE}}': config['main_executable'],
        '{{APP_ICON_B64}}': config['icon_b64'],
        '{{FILES_ARCHIVE_B64}}': config['archive_b64'],
        '{{INSTALL_SIZE_MB}}': str(config['install_size_mb']),
    }

    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)

    return template


def check_dependencies():
    """Проверка необходимых библиотек"""
    missing = []
    for lib in ['customtkinter', 'pyinstaller']:
        try:
            __import__(lib.replace('-', '_'))
        except ImportError:
            if lib == 'pyinstaller':
                try:
                    __import__('PyInstaller')
                except ImportError:
                    missing.append(lib)
            else:
                missing.append(lib)

    if missing:
        print_warning(f"Не установлены: {', '.join(missing)}")
        install = input_styled(
            "Установить автоматически? (y/n)", "y"
        ).lower()
        if install == 'y':
            for lib in missing:
                print_info(f"Установка {lib}...")
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', lib],
                    capture_output=True
                )
            print_success("Зависимости установлены!")
        else:
            print_warning("Компиляция в .exe может не сработать")


def compile_to_exe(script_path, icon_path, output_name):
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name', output_name,
        '--clean',
        '--noconfirm',
    ]

    # UAC манифест - запрос прав администратора
    manifest = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="requireAdministrator"
                                 uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
</assembly>'''

    manifest_path = os.path.join(
        os.path.dirname(script_path), f"{output_name}.manifest"
    )
    with open(manifest_path, 'w') as f:
        f.write(manifest)

    cmd.extend(['--manifest', manifest_path])

    if icon_path and os.path.isfile(icon_path):
        cmd.extend(['--icon', icon_path])

    cmd.extend([
        '--hidden-import', 'customtkinter',
        '--collect-all', 'customtkinter',
    ])

    cmd.append(script_path)

    print_info("Запуск PyInstaller...")
    print(f"  {Colors.DIM}$ {' '.join(cmd[:8])}...{Colors.END}\n")

    result = subprocess.run(cmd, capture_output=False)

    # Очистка манифеста
    if os.path.isfile(manifest_path):
        os.unlink(manifest_path)

    return result.returncode == 0


def main():
    clear_screen()
    print_banner()

    TOTAL_STEPS = 6

    # Проверка зависимостей
    print_info("Проверка зависимостей...")
    check_dependencies()

    # ══════════════ Шаг 1 ══════════════
    print_step(1, TOTAL_STEPS, "Информация о приложении")

    app_name = input_styled("Название приложения", "MyApp")
    app_version = input_styled("Версия", "1.0.0")
    app_author = input_styled("Автор", "Developer")
    app_description = input_styled(
        "Описание", f"{app_name} - отличное приложение!"
    )

    print_success(f"Приложение: {app_name} v{app_version} by {app_author}")

    # ══════════════ Шаг 2 ══════════════
    print_step(2, TOTAL_STEPS, "Файлы для упаковки")

    while True:
        source_folder = input_styled(
            "Папка с файлами приложения (полный путь)"
        )
        if os.path.isdir(source_folder):
            break
        print_error(f"Папка не найдена: {source_folder}")

    files = list_files_in_folder(source_folder)
    size_mb = get_folder_size(source_folder)

    print_success(f"Найдено файлов: {len(files)}")
    print_success(f"Общий размер: {size_mb} МБ")

    print(f"\n  {Colors.DIM}Содержимое:{Colors.END}")
    for name, size in files[:15]:
        size_str = f"{size / 1024:.1f} KB" if size < 1048576 \
                   else f"{size / 1048576:.1f} MB"
        print(f"  {Colors.DIM}  📄 {name} ({size_str}){Colors.END}")
    if len(files) > 15:
        print(f"  {Colors.DIM}  ... и ещё {len(files) - 15} файлов{Colors.END}")

    # ══════════════ Шаг 3 ══════════════
    print_step(3, TOTAL_STEPS, "Главный исполняемый файл")

    exe_files = [
        f for f, _ in files
        if f.endswith(('.exe', '.bat', '.cmd', '.py', '.pyw'))
    ]

    if exe_files:
        print_info("Найдены исполняемые файлы:")
        for i, f in enumerate(exe_files, 1):
            print(f"    {Colors.CYAN}{i}.{Colors.END} {f}")

    main_executable = input_styled(
        "Главный файл для запуска",
        exe_files[0] if exe_files else "app.exe"
    )
    print_success(f"Главный файл: {main_executable}")

    # ══════════════ Шаг 4 ══════════════
    print_step(4, TOTAL_STEPS, "Иконка приложения")

    icon_path = input_styled(
        "Путь к .ico файлу (Enter = без иконки)", ""
    )

    icon_b64 = ""
    if icon_path and os.path.isfile(icon_path):
        icon_b64 = encode_icon(icon_path)
        print_success(f"Иконка загружена: {icon_path}")
    else:
        print_info("Установщик будет без кастомной иконки")
        icon_path = ""

    # ══════════════ Шаг 5 ══════════════
    print_step(5, TOTAL_STEPS, "Сборка установщика")

    print_info("Создание архива файлов...")
    archive_b64 = create_archive(source_folder)
    archive_size_mb = round(len(archive_b64) * 3 / 4 / 1048576, 1)
    print_success(f"Архив создан: {archive_size_mb} МБ (сжатый)")

    config = {
        'app_name': app_name,
        'app_version': app_version,
        'app_author': app_author,
        'app_description': app_description,
        'main_executable': main_executable,
        'icon_b64': icon_b64,
        'archive_b64': archive_b64,
        'install_size_mb': size_mb,
    }

    print_info("Генерация скрипта установщика...")
    installer_script = build_installer_script(config)

    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "output"
    )
    os.makedirs(output_dir, exist_ok=True)

    script_name = f"{app_name}_Setup"
    script_path = os.path.join(output_dir, f"{script_name}.py")

    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(installer_script)

    print_success(f"Скрипт сохранён: {script_path}")

    # ══════════════ Шаг 6 ══════════════
    print_step(6, TOTAL_STEPS, "Компиляция в .exe")

    compile_choice = input_styled(
        "Скомпилировать в .exe? (y/n)", "y"
    ).lower()

    if compile_choice == 'y':
        print_info("Компиляция... Это может занять несколько минут ⏳")
        print_info("Установщик будет запрашивать права администратора 🛡️")

        success = compile_to_exe(script_path, icon_path, script_name)

        if success:
            exe_path = os.path.join("dist", f"{script_name}.exe")
            if os.path.isfile(exe_path):
                final_exe = os.path.join(output_dir, f"{script_name}.exe")
                shutil.move(exe_path, final_exe)
                exe_size = os.path.getsize(final_exe) / 1048576
                print_success(f"EXE создан: {final_exe}")
                print_success(f"Размер: {exe_size:.1f} МБ")
                print_success("🛡️ Будет запрашивать права администратора")
            else:
                print_error("EXE файл не найден")
        else:
            print_error("Ошибка компиляции!")

        # Очистка
        for cleanup in ['build', 'dist']:
            if os.path.isdir(cleanup):
                shutil.rmtree(cleanup, ignore_errors=True)
        spec_file = f'{script_name}.spec'
        if os.path.isfile(spec_file):
            os.remove(spec_file)
    else:
        print_info("Компиляция пропущена")
        print_info(f"Запустите: python \"{script_path}\"")

    # ══════════════ Готово! ══════════════
    print(f"""
{Colors.GREEN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   ✅  УСТАНОВЩИК УСПЕШНО СОЗДАН!                         ║
║                                                           ║
║   📁 Результат: output/                                  ║
║   📄 Скрипт:    {script_name}.py                         ║
║   🛡️  UAC:      Запрашивает права администратора         ║
║   🖥️  Ярлык:    Создаётся на рабочем столе              ║
║                                                           ║
║   Особенности:                                            ║
║   • Автозапрос прав администратора (UAC)                  ║
║   • 3 метода создания ярлыков (COM/PowerShell/VBS)        ║
║   • Ярлык на рабочем столе + меню Пуск                   ║
║   • Красивый GUI на CustomTkinter                         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
{Colors.END}""")


if __name__ == "__main__":
    main()