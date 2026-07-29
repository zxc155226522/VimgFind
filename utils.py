from pathlib import Path
from queue import Queue, Empty
from threading import Thread, current_thread
import threading
from typing import Callable
from collections import namedtuple
import datetime
import logging
import unicodedata
import os
import subprocess
import functools
import ctypes
import hashlib
import sys
import io
import uuid
import shutil



import win32clipboard
import win32con
from tkinter import Tk
from PIL import Image, ImageTk, ImageOps, UnidentifiedImageError
from PIL.Image import DecompressionBombError
from PIL.ImageFile import ImageFile



from setting import Setting




class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", ctypes.c_uint),
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
        ("fNC", ctypes.c_int),
        ("fWide", ctypes.c_int),
    ]



class Decorator(object):
    """线程安全的队列流，每个线程独立的 stdout/stderr"""
    _thread_streams = {}
    _thread_streams_lock = threading.Lock()
    progress_queue = Queue()

    @classmethod
    def _get_thread_stream(cls) -> "QueueStream":
        tid = current_thread().ident
        with cls._thread_streams_lock:
            if tid not in cls._thread_streams:
                cls._thread_streams[tid] = QueueStream(cls.progress_queue)
            return cls._thread_streams[tid]

    @staticmethod
    def send_task(target):# -> _Wrapped[Callable[..., Any], Any, Callable[..., Any], None]:
        @functools.wraps(target)
        def inner(*args, **kwargs):
            thread = Thread(
                target=target,
                args=args,
                kwargs=kwargs,
                daemon=True
            )
            thread.start()
        return inner

    @staticmethod
    def redirect_output(target: Callable) -> Callable:
        def inner(*args, **kwargs) -> None:
            original_stdout = sys.stdout
            original_stderr = sys.stderr

            thread_stream = Decorator._get_thread_stream()
            sys.stdout = thread_stream
            sys.stderr = thread_stream

            try:
                target(*args, **kwargs)
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr
        return inner



class FileOperation(object):
    @staticmethod
    def get_file_iterator(target_dir) -> tuple[list[str], int]:
        files = []
        for file_path in Path(target_dir).rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in Setting.accepted_exts:
                files.append(str(file_path))
        return files, len(files)

    @staticmethod
    def open_file(file_path: str | Path, highlight: bool = False) -> None:
        file_path = Path(file_path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在：{file_path}")

        command: list[str] = []
        if highlight:
            command = ["explorer.exe", "/select,", str(file_path)]
        else:
            command = ["explorer.exe", str(file_path)]
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            if result.stderr:
                logging.error(f"[警告] 打开文件时产生提示：{result.stderr.strip()}")
        except subprocess.CalledProcessError as e:
            logging.error(f"打开文件失败：命令 {' '.join(command)} 执行错误，详情：{e.stderr}")
        except FileNotFoundError:
            logging.error(f"打开文件失败：未找到命令 {' '.join(command)}，请检查系统配置")
        except Exception as e:
            logging.error(f"打开文件时发生未知错误：{str(e)}")

    @staticmethod
    def copy_files(*file_paths: str | Path) -> None:
        valid_paths = []

        for path in file_paths:
            abs_path = Path(path).absolute()
            if abs_path.exists() and abs_path.is_file():
                valid_paths.append(str(abs_path).replace("/", "\\") + "\0")

        if not valid_paths:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.CloseClipboard()
            return

        paths_str = "".join(valid_paths) + "\0"
        paths_wchar = paths_str.encode("utf-16le")
        
        df = DROPFILES()
        df.pFiles = ctypes.sizeof(DROPFILES)
        df.fWide = 1
        buffer = ctypes.string_at(ctypes.pointer(df), ctypes.sizeof(df)) + paths_wchar

        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_HDROP, buffer)
        except Exception as e:
            logging.error(f"写入剪贴板失败：{e}")
        finally:
            win32clipboard.CloseClipboard()

    @staticmethod
    def copy_filepaths(*file_paths: str | Path, tk: Tk) -> None:
        tk.clipboard_clear()
        tk.clipboard_append("\n".join([str(i) for i in file_paths]))

    @staticmethod
    def delete_file(file_path: str | Path) -> None:
        try:
            os.remove(file_path)
        except (FileNotFoundError, OSError) as e:
            logging.error(f"删除文件失败: {file_path}")

    @staticmethod
    def save_as(src_path: str | Path, dest_path: str | Path, is_binary: bool = False, inplace=True) -> bool:
        src_path = Path(src_path)
        dest_path = Path(dest_path)
        if not src_path.exists() or src_path.is_dir() or dest_path.is_dir():
            return False
        read_mode = 'rb' if is_binary else 'r'
        write_mode = 'wb' if is_binary else 'w'
        encoding = None if is_binary else 'utf-8'
        try:
            with open(src_path, mode=read_mode, encoding=encoding) as f_src:
                content = f_src.read()
            dest_path = dest_path if inplace else FileOperation.generate_copy_name(dest_path)
            with open(dest_path, mode=write_mode, encoding=encoding) as f_dst:
                f_dst.write(content)
            return True
        except (PermissionError, OSError):
            return False

    @staticmethod
    def save_to_dir(*src_paths: str | Path, dest_dir: str | Path, is_binary: bool = False, inplace=True) -> bool:
        if dest_dir == "":
            return False
        dest_dir = Path(dest_dir)
        if not dest_dir.exists() or not dest_dir.is_dir():
            return False
        all_finish = True
        for src_path in src_paths:
            ans = FileOperation.save_as(src_path, dest_dir / Path(src_path).name, is_binary, inplace)
            if not ans:
                all_finish = False
        return all_finish

    @staticmethod
    def clear_folder_all(target_dir: str | Path) -> None:
        target_dir = Path(target_dir)
        if not target_dir.exists() or not target_dir.is_dir():
            return
        
        for item_path in target_dir.glob("*"):
            try:
                if item_path.is_file() or item_path.is_symlink():
                    os.remove(item_path)
                elif item_path.is_dir():
                    shutil.rmtree(item_path)
            except PermissionError:
                logging.error(f"权限不足，无法删除：{item_path}")
            except FileNotFoundError:
                return
            except Exception as e:
                logging.error(f"删除失败 {item_path}：{str(e)}")

    @staticmethod
    def truncate_filename(filename: str, target_width: int = 16) -> str:
        file_path = Path(filename)
        char_width = lambda x: 2 if unicodedata.east_asian_width(x) in ('F', 'W') else 1
        target_width = target_width - sum(char_width(char) for char in file_path.suffix) - 1
        curr_width = 0
        for idx, char in enumerate(file_path.stem):
            curr_width += char_width(char)
            if curr_width > target_width:
                return f"{file_path.stem[:idx]}~{file_path.suffix}"
        return str(file_path.name)

    @staticmethod
    def get_metainfo(file_path: str | Path) -> int:
        file_size = os.path.getsize(file_path)
        return file_size

    @staticmethod
    def generate_unique_filename(target_dir: Path, suffix: str) -> Path:
        random_name = uuid.uuid4().hex
        if suffix and not suffix.startswith("."):
            suffix = f".{suffix}"
        filename = f"{random_name}{suffix}"
        full_path = target_dir / filename
        max_attempts = 10
        attempts = 0
        while full_path.exists() and attempts < max_attempts:
            random_name = uuid.uuid4().hex
            filename = f"{random_name}{suffix}"
            full_path = target_dir / filename
            attempts += 1
        
        if attempts >= max_attempts:
            raise RuntimeError("超出最大尝试次数，无法生成唯一文件名")
        
        return full_path

    @staticmethod
    def generate_copy_name(file_path: str | Path) -> Path:
        orig_file_path = curr_file_path = Path(file_path)
        suffix_num = 2
        while curr_file_path.exists():
            curr_file_path = orig_file_path.with_stem(f"{orig_file_path.stem} ({suffix_num})")
            suffix_num += 1
        return curr_file_path
    
    @staticmethod
    def extract_file_paths(text: str) -> list[str]:
        paths = []
        i = 0
        n = len(text)
        while i < n:
            while i < n and text[i].isspace():
                i += 1
            if i >= n:
                break
            if text[i] == '{':
                brace_count = 1
                j = i + 1
                while j < n and brace_count > 0:
                    if text[j] == '{':
                        brace_count += 1
                    elif text[j] == '}':
                        brace_count -= 1
                    j += 1
                if brace_count == 0:
                    path = text[i+1:j-1]
                    paths.append(path.strip())
                    i = j
                else:
                    j = i + 1
                    while j < n and not text[j].isspace():
                        j += 1
                    path = text[i:j].strip()
                    if path:
                        paths.append(path)
                    i = j
            else:
                j = i
                while j < n and not text[j].isspace():
                    j += 1
                path = text[i:j].strip()
                if path:
                    paths.append(path)
                i = j
        
        return paths



class ImageOperation(object):
    @staticmethod
    def get_clipboard_image_bytes() -> None | ImageFile:
        try:
            win32clipboard.OpenClipboard()
            if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                return None
            dib_data = win32clipboard.GetClipboardData(win32con.CF_DIB)
            return Image.open(io.BytesIO(dib_data))
        except Exception as e:
            return None
        finally:
            win32clipboard.CloseClipboard()

    @staticmethod
    def get_image_obj(image_path: str | Path) -> ImageFile | None:
        try:
            return Image.open(image_path)
        except (UnidentifiedImageError, DecompressionBombError, OSError, FileNotFoundError, MemoryError) as e:
            logging.error(f"加载图片失败，已跳过 {image_path}: {e}")
            return
        


LoaderResult = namedtuple("LoaderResult", ["item", "size", "photo", "error"])
class ImageLoader:
    THUMB_CACHE_DIR = Path("./temp/thumbnails")
    MAX_CACHE_SIZE = 200 * 1024 * 1024
    THUMBNAIL_FILE_SIZE_LIMIT = 3 * 1024 * 1024

    def __init__(self) -> None:
        self.THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.task_queue: Queue[tuple] = Queue()
        self.result_queue: Queue[LoaderResult] = Queue()
        self.threads: list[Thread] = []
        self.running = True
        for _ in range(10):
            thread = Thread(target=self._worker, daemon=True)
            thread.start()
            self.threads.append(thread)
    
    def add_task(self, item: str, image_path: str, thumbnail_size: int) -> None:
        self.task_queue.put((item, image_path, thumbnail_size))
    
    def _get_cache_key(self, image_path: str, thumbnail_size: int) -> str:
        raw = f"{os.path.normpath(image_path)}:{thumbnail_size}"
        return hashlib.md5(raw.encode()).hexdigest()
    
    def _check_cache(self, image_path: str, cache_key: str) -> ImageTk.PhotoImage | None:
        cache_file = self.THUMB_CACHE_DIR / f"{cache_key}.png"
        if not cache_file.exists():
            return None
        try:
            orig_mtime = os.path.getmtime(image_path)
            cache_mtime = os.path.getmtime(cache_file)
            if orig_mtime > cache_mtime:
                cache_file.unlink(missing_ok=True)
                return None
        except OSError:
            return None
        try:
            img = Image.open(cache_file)
            return ImageTk.PhotoImage(img)
        except Exception:
            cache_file.unlink(missing_ok=True)
            return None
    
    def _save_to_cache(self, img: Image.Image, cache_key: str) -> None:
        self._maybe_clean_cache()
        try:
            cache_file = self.THUMB_CACHE_DIR / f"{cache_key}.png"
            img.save(cache_file, "PNG")
        except Exception:
            pass
    
    def _maybe_clean_cache(self) -> None:
        try:
            total_size = sum(
                f.stat().st_size for f in self.THUMB_CACHE_DIR.glob("*.png")
                if f.is_file()
            )
            if total_size > self.MAX_CACHE_SIZE:
                files = sorted(
                    self.THUMB_CACHE_DIR.glob("*.png"),
                    key=lambda f: f.stat().st_mtime
                )
                for f in files[:len(files) // 2]:
                    try:
                        f.unlink()
                    except OSError:
                        pass
        except Exception:
            pass
    
    def _worker(self) -> None:
        while self.running:
            try:
                item, image_path, thumbnail_size = self.task_queue.get(timeout=1)
            except Exception:
                continue

            raw_size = (0, 0)
            try:
                use_thumbnail = os.path.getsize(image_path) > self.THUMBNAIL_FILE_SIZE_LIMIT
            except OSError:
                use_thumbnail = True
            cache_key = self._get_cache_key(image_path, thumbnail_size) if use_thumbnail else ""
            cached_photo = self._check_cache(image_path, cache_key) if use_thumbnail else None
            if cached_photo is not None:
                img = ImageOperation.get_image_obj(image_path)
                if img is not None:
                    raw_size = img.size
                self.result_queue.put(LoaderResult(
                    item=item, size=raw_size, photo=cached_photo, error=""
                ))
                self.task_queue.task_done()
                continue

            img = ImageOperation.get_image_obj(image_path)
            if img is None:
                self.result_queue.put(LoaderResult(
                    item=item, size=(0, 0), photo=None, error="加载图片失败！"
                ))
            else:
                try:
                    raw_size = img.size
                    img.thumbnail((thumbnail_size, thumbnail_size))
                    img = ImageOps.exif_transpose(img)
                    photo = ImageTk.PhotoImage(img)
                    if use_thumbnail:
                        self._save_to_cache(img, cache_key)
                    self.result_queue.put(LoaderResult(
                        item=item,
                        size=raw_size, 
                        photo=photo, 
                        error=""
                    ))
                except Exception as e:
                    logging.error(f"加载缩略图失败，已跳过 {image_path}: {e}")
                    self.result_queue.put(LoaderResult(
                        item=item, size=(0, 0), photo=None, error="加载图片失败！"
                    ))
            self.task_queue.task_done()
                
    def get_results(self) -> list[LoaderResult]:
        results = []
        while not self.result_queue.empty():
            results.append(self.result_queue.get_nowait())
        return results
    
    def stop(self) -> None:
        self.running = False
        for thread in self.threads:
            thread.join(timeout=1)




class QueueStream:
    def __init__(self, queue: Queue) -> None:
        self.queue = queue

    def write(self, message: str) -> None:
        clean_message = message.replace('\r', '').replace('\n', '').strip()
        if clean_message:
            self.queue.put(clean_message)

    def flush(self) -> None:
        pass



class DatabaseBackup:
    BACKUP_DIR = Path("./config/backups")
    RETENTION_DAYS = 30
    BACKUP_FILES = (
        Path("./config/setting.json"),
        Path("./config/index/vector_index.bin"),
        Path("./config/index/name_index.json"),
    )

    def __init__(self) -> None:
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _today_name() -> str:
        return datetime.date.today().isoformat()

    @staticmethod
    def _parse_date(backup_name: str) -> datetime.date | None:
        try:
            return datetime.date.fromisoformat(backup_name)
        except ValueError:
            return None

    def today_backup_path(self) -> Path:
        return self.BACKUP_DIR / self._today_name()

    def _copy_file(self, src: Path, dst_dir: Path) -> bool:
        if not src.exists():
            return False
        dst = dst_dir / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True

    def backup(self) -> bool:
        today_path = self.today_backup_path()
        if today_path.exists():
            shutil.rmtree(today_path)
        today_path.mkdir(parents=True, exist_ok=True)
        success_count = sum(
            self._copy_file(f, today_path) for f in self.BACKUP_FILES
        )
        return success_count > 0

    def restore(self, backup_name: str) -> bool:
        backup_path = self.BACKUP_DIR / backup_name
        if not backup_path.exists() or not backup_path.is_dir():
            return False
        self.backup()
        for src_file in self.BACKUP_FILES:
            backup_file = backup_path / src_file.name
            if backup_file.exists():
                shutil.copy2(backup_file, src_file)
        return True

    def cleanup(self) -> int:
        cutoff = datetime.date.today() - datetime.timedelta(days=self.RETENTION_DAYS)
        removed = 0
        for entry in self.BACKUP_DIR.iterdir():
            if not entry.is_dir():
                continue
            backup_date = self._parse_date(entry.name)
            if backup_date is None or backup_date < cutoff:
                shutil.rmtree(entry)
                removed += 1
        return removed

    def get_backup_list(self) -> list[str]:
        if not self.BACKUP_DIR.exists():
            return []
        backups = []
        for entry in self.BACKUP_DIR.iterdir():
            if not entry.is_dir():
                continue
            if self._parse_date(entry.name) is not None:
                backups.append(entry.name)
        backups.sort(reverse=True)
        return backups


