from tkinter import messagebox, filedialog
from ttkbootstrap import Style, Treeview
from tkinterdnd2 import DND_FILES, TkinterDnD
import tkinter as tk
from pathlib import Path
from typing import Literal
from queue import Empty
import datetime
import os
import sys
import subprocess
import logging
import ctypes
import io
import re
import winreg

try:
    import psutil
except ImportError:
    psutil = None
import win32clipboard
import win32con

from ui import WinGUI
from widgets import BasicImagePreviewView, DetailListView, ThumbnailGridView
from setting import Setting, WinInfo
from utils import FileOperation, ImageOperation, Decorator
from utils import DROPFILES
from search_tools import SearchTool
import webbrowser


from PIL import Image


class CoreControl(WinGUI):
    def __init__(self) -> None:
        super().__init__()
        self.setting = Setting()
        self.__change_theme(setting_theme=True)
        self.search_tools = SearchTool(self.setting)
        self._process_monitor = psutil.Process(os.getpid()) if psutil else None
        if self._process_monitor:
            self._process_monitor.cpu_percent(interval=None)
        self.result_count_entry.delete(0, tk.END)
        self.result_count_entry.insert(0, str(self.setting.get_config("index", "max_match_count") or 100))
        self.index_table_control = IndexTableControl(self)
        self.search_control = SearchControl(self)
        self.menu_control = MenuControl(self)
        self.search_control.set_preview_mode(self.setting.get_config("function", "preview_mode"))
        self.__env_init()
        self.bind_event(first_time=True)
        
    def bind_event(self, first_time=False) -> None:
        # 搜索展示控制项
        self.preview_view.bind("<<ItemviewSelect>>", self.search_control.preview_found_image)
        self.preview_view.bind("<Control-a>", lambda e: self.preview_view.selection_set(tk.ALL))
        self.preview_view.bind("<Control-v>", lambda e: self.search_control.search_image_by_clipboard())
        self.__bind_preview_item_actions()
        preview_widgets = (self.preview_canvas1, self.preview_canvas2, self.preview_view)
        for w in preview_widgets:
            w.bind("<Button-3>", lambda e, w=w: self.menu_control.create_right_click_menu(e, w))
            w.bind("<Double-Button-1>", lambda e, w=w: self.menu_control.double_click_open_file(e, w))

        if not first_time:
            return
        
        # 搜索输入控制项
        self.search_by_browser_btn.config(command=self.search_control.search_by_browser)
        self.search_by_clipboard_btn.config(command=self.search_control.search_image_by_clipboard)
        self.path_filter_btn.config(command=self.search_control.create_path_filter_menu)
        self.search_entry.bind("<Return>", lambda e: self.search_control.search_image_by_text())
        self.search_btn.config(command=lambda: self.search_control.search_image_by_text())
        self.search_entry.bind("<<Paste>>", self.__on_search_entry_paste)
        self.search_entry.bind("<FocusOut>", lambda e: self.after(50, self.search_entry.focus_set))
        self.result_count_entry.bind("<Return>", self.search_control.apply_result_count_from_entry)
        self.result_count_entry.bind("<FocusOut>", self.search_control.apply_result_count_from_entry)
        self.preview_detail_btn.config(command=lambda: self.search_control.set_preview_mode("detail_info"))
        self.preview_icon_btn.config(command=lambda: self.search_control.set_preview_mode("medium_ico"))
        
        # 索引设置项
        self.index_dataset_table.bind("<Double-Button-1>", self.menu_control.double_click_open_file)
        self.add_index_button.config(command=self.index_table_control.add_search_dir)
        self.update_index_button.config(command=self.index_table_control.sync_index)
        self.delete_index_button.config(command=self.index_table_control.delete_search_dir)
        self.rebuild_index_button.config(command=self.index_table_control.rebuild_index)

        # 常规设置项
        self.theme_combobox.bind("<<ComboboxSelected>>", lambda e: self.__change_theme())
        self.open_setting_file_button.config(command=lambda: FileOperation.open_file(Setting.config_path))
        self.open_repertory_button.config(command=lambda: webbrowser.open(r"https://github.com/Just-A-Freshman/VimgFind"))
        self.__init_autostart_button()

        # 全局事件处理
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.__on_drop)

    def __bind_preview_item_actions(self) -> None:
        if not isinstance(self.preview_view, ThumbnailGridView):
            return
        self.preview_view.copy_image_callback = self.menu_control.copy_file_image_async
        self.preview_view.copy_path_callback = self.menu_control.copy_file_path_async
        self.preview_view.open_ps_callback = self.menu_control.open_file_with_photoshop_async

    @Decorator.send_task
    def __env_init(self) -> None:
        self.index_table_control.refresh_index_dataset_table()
        self.update_threads_count_scale.set(value=self.setting.get_config("function", "max_work_thread"))
        # 显示设备信息
        self.__update_device_info()
        self.__update_performance_info()
        if self.setting.get_config("function", "auto_update_index"):
            self.auto_update_btn.invoke()
            self.index_table_control.sync_index(show_message=False)
        else:
            self.index_table_control.update_index_tip()
        self.after(self.setting.schedule_save_interval, self.__schedule_save)

    def __update_device_info(self) -> None:
        """读取编码器设备信息并显示到界面上"""
        try:
            device = self.search_tools.get_device_info()
            self.device_info_label.config(text=f"推理设备：{device}")
        except Exception:
            self.device_info_label.config(text="推理设备：未知")

    def __update_performance_info(self) -> None:
        """定时刷新 CPU、内存和 GPU 占用信息"""
        try:
            parts = []
            if self._process_monitor is not None and psutil is not None:
                cpu_percent = self._process_monitor.cpu_percent(interval=None)
                memory_info = self._process_monitor.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                system_memory_percent = psutil.virtual_memory().percent
                parts.append(f"CPU {cpu_percent:.1f}% | 内存 {memory_mb:.0f}MB ({system_memory_percent:.1f}%)")
            else:
                parts.append("CPU --% | 内存 --MB")
            gpu_info = self._get_gpu_info()
            if gpu_info:
                parts.append(gpu_info)
            self.performance_info_label.config(text="性能：" + " | ".join(parts))
        except Exception:
            self.performance_info_label.config(text="性能：不可用")
        finally:
            self.after(1000, self.__update_performance_info)

    @staticmethod
    def _get_gpu_info() -> str:
        """通过 nvidia-smi 获取 GPU 利用率和显存占用"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode != 0 or not result.stdout.strip():
                return ""
            parts = result.stdout.strip().split(",")
            if len(parts) >= 3:
                gpu_util = parts[0].strip()
                mem_used = parts[1].strip()
                mem_total = parts[2].strip()
                return f"GPU {gpu_util}% | 显存 {mem_used}/{mem_total}MB"
        except Exception:
            pass
        return ""

    def __change_theme(self, setting_theme=False) -> None:
        style = Style()
        if setting_theme:
            valid_theme_names = style.theme_names()
            valid_theme_name = self.setting.get_config("function", "ui_style")
            valid_theme_name = valid_theme_name if valid_theme_name in valid_theme_names else "superhero"
            self.theme_combobox.current(valid_theme_names.index(valid_theme_name))
        theme_cbo_value = self.theme_combobox.get()
        self.theme_combobox.selection_clear()
        # 配置特殊Style
        style.theme_use(theme_cbo_value)
        style.configure('TNotebook.Tab', font=('微软雅黑', 12))
        style.configure("Treeview", rowheight=50)

    def __on_drop(self, event: TkinterDnD.DnDEvent) -> None:
        file_paths_str: str = getattr(event, "data")
        file_paths = FileOperation.extract_file_paths(file_paths_str)
        tab_id = self.switch_tab.index(self.switch_tab.select())
        if tab_id == 0:
            self.search_control.search_by_browser(file_paths[0])
        elif tab_id == 1:
            for dir_path in file_paths:
                self.index_table_control.add_search_dir(dir_path)

    def __on_search_entry_drop(self, event: TkinterDnD.DnDEvent) -> None:
        """搜索输入框拖放图片文件（不显示路径在搜索框）"""
        file_paths_str: str = getattr(event, "data")
        file_paths = FileOperation.extract_file_paths(file_paths_str)
        if file_paths:
            self.search_control.search_by_browser(file_paths[0])

    def __on_search_entry_paste(self, event: tk.Event) -> None:
        """搜索框 Ctrl+V/Win+V 粘贴：检测图片路径或图片数据，自动搜索"""
        self.after_idle(self._do_search_entry_paste)

    def _do_search_entry_paste(self) -> None:
        """检查剪贴板：1.CF_HDROP文件路径 2.CF_DIB图片数据 3.CF_UNICODETEXT文本路径。搜索后焦点回到搜索框"""
        self.search_entry.delete(0, tk.END)
        try:
            win32clipboard.OpenClipboard()
        except Exception:
            self.search_entry.focus_set()
            return
        try:
            # 1. 优先检查文件路径（CF_HDROP）
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                hdrop = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                df = DROPFILES.from_buffer_copy(hdrop[:ctypes.sizeof(DROPFILES)])
                data = hdrop[df.pFiles:]
                paths_str = data.decode("utf-16le", errors="replace").strip("\0")
                paths = [p for p in paths_str.split("\0") if p.strip()]
                if paths:
                    first_path = paths[0]
                    if Path(first_path).suffix.lower() in Setting.accepted_exts:
                        self.search_control.search_by_browser(first_path)
                        return
            # 2. 文本路径（CF_UNICODETEXT）
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT).strip()
                if text:
                    path = Path(text)
                    if path.is_file() and path.suffix.lower() in Setting.accepted_exts:
                        self.search_control.search_by_browser(text)
                        return
        except Exception:
            pass
        finally:
            win32clipboard.CloseClipboard()
        # 3. 图片位图数据（CF_DIB）—— 必须在关闭外层剪贴板之后，由内部方法自行 Open/Close
        image_obj = ImageOperation.get_clipboard_image_bytes()
        if image_obj is not None:
            self.search_control.search_image_by_clipboard()
        self.search_entry.focus_set()

    def __schedule_save(self) -> None:
        self.search_tools.save_index()
        self.after(self.setting.schedule_save_interval, self.__schedule_save)

    def __init_autostart_button(self) -> None:
        if self.__is_autostart_enabled():
            self.autostart_btn.state(['selected'])
        self.autostart_btn.config(command=self.__toggle_autostart)

    def __toggle_autostart(self) -> None:
        self.__set_autostart(self.autostart_btn.instate(['selected']))

    _AUTOSTART_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def __is_autostart_enabled(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._AUTOSTART_REG_PATH) as key:
                winreg.QueryValueEx(key, WinInfo.title)
                return True
        except FileNotFoundError:
            return False
        except OSError:
            return False

    def __set_autostart(self, enabled: bool) -> None:
        if enabled:
            if not getattr(sys, 'frozen', False):
                messagebox.showwarning("提示", "脚本模式下不支持设置开机启动，请使用打包后的程序。")
                self.autostart_btn.state(['!selected'])
                return
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._AUTOSTART_REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, WinInfo.title, 0, winreg.REG_SZ, f'"{sys.executable}"')
            except OSError as e:
                messagebox.showerror("错误", f"设置开机启动失败：{e}")
                self.autostart_btn.state(['!selected'])
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._AUTOSTART_REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, WinInfo.title)
            except FileNotFoundError:
                pass
            except OSError as e:
                messagebox.showerror("错误", f"取消开机启动失败：{e}")
                self.autostart_btn.state(['selected'])
    
    def destroy(self) -> None:
        try:
            self.setting.modity_config("function", "ui_style", self.theme_combobox.get())
            self.setting.modity_config("function", "auto_update_index", self.auto_update_btn.instate(['selected']))
            self.setting.modity_config("function", "max_work_thread", int(float(self.update_threads_count_scale.get())))
            self.setting.save_settings()
            self.setting.clean_log()
            self.search_tools.destroy()
            self.search_tools.save_index()
            FileOperation.clear_folder_all(Setting.temp_image_path)
            self.search_tools.set_force_end_update(True)
        except Exception as e:
            messagebox.showerror("错误", str(e))
        finally:
            super().destroy()



class SearchControl(object):
    def __init__(self, core_control: CoreControl) -> None:
        self._last_search_content: Image.Image | str = ""
        self._is_finish_search: bool = True
        self._is_name_search: bool = True
        self._preview_timer: str = ""
        self._switching_mode: bool = False
        self._selected_search_dirs: set[str] = set()
        self.core_control = core_control

    def create_path_filter_menu(self) -> None:
        search_dirs = self.core_control.setting.get_config("index", "search_dir") or []
        valid_dirs = [str(Path(search_dir)) for search_dir in search_dirs if Path(search_dir).exists()]
        self._selected_search_dirs.intersection_update(valid_dirs)

        menu = tk.Menu(tearoff=0, activeborderwidth=MenuControl.ACTIVE_BORDER_WIDTH)
        menu.add_command(label="全部路径", command=self.clear_path_filter)
        if valid_dirs:
            menu.add_separator()
        for search_dir in valid_dirs:
            selected = tk.BooleanVar(value=search_dir in self._selected_search_dirs)
            menu.add_checkbutton(
                label=search_dir,
                variable=selected,
                command=lambda d=search_dir: self.toggle_path_filter(d)
            )
        menu.post(
            self.core_control.path_filter_btn.winfo_rootx(),
            self.core_control.path_filter_btn.winfo_rooty() + self.core_control.path_filter_btn.winfo_height()
        )
        menu.bind("<Unmap>", lambda e: menu.destroy())

    def toggle_path_filter(self, search_dir: str) -> None:
        if search_dir in self._selected_search_dirs:
            self._selected_search_dirs.remove(search_dir)
        else:
            self._selected_search_dirs.add(search_dir)
        self._update_path_filter_button()
        if self._last_search_content:
            self.__search_image(self._last_search_content)

    def clear_path_filter(self) -> None:
        self._selected_search_dirs.clear()
        self._update_path_filter_button()
        if self._last_search_content:
            self.__search_image(self._last_search_content)

    def _update_path_filter_button(self) -> None:
        selected_count = len(self._selected_search_dirs)
        text = "路径: 全部" if selected_count == 0 else f"路径: {selected_count}项"
        self.core_control.path_filter_btn.config(text=text)

    def _is_in_selected_dirs(self, image_path: str) -> bool:
        if not self._selected_search_dirs:
            return True
        image_path_obj = Path(image_path).resolve()
        for search_dir in self._selected_search_dirs:
            try:
                if image_path_obj.is_relative_to(Path(search_dir).resolve()):
                    return True
            except ValueError:
                continue
        return False

    @Decorator.send_task
    def search_by_browser(self, image_path: str | None = None) -> None:
        if image_path is not None and not Path(image_path).is_file():
            return
        if not image_path:
            image_path = filedialog.askopenfilename(
                filetypes=[("图片文件", "*" + ";*".join(Setting.accepted_exts))]
            )
            if not image_path:
                return
        image_obj = ImageOperation.get_image_obj(image_path)
        if image_obj is None:
            messagebox.showwarning("警告", "无法识别该图片类型！")
            return
        self.core_control.after(0, lambda p=image_path, o=image_obj: 
            self.core_control.preview_canvas1.append_result(p, o))
        self.__search_image(image_obj)

    @Decorator.send_task
    def search_image_by_clipboard(self) -> None:
        image_obj = ImageOperation.get_clipboard_image_bytes()
        if image_obj is None:
            try:
                image_path = Path(self.core_control.clipboard_get())
                image_obj = ImageOperation.get_image_obj(image_path)
                if image_obj is None:
                    raise tk.TclError
            except tk.TclError:
                messagebox.showinfo("提示", "无法识别剪切板中的图片数据！")
                return
        else:
            image_path = FileOperation.generate_unique_filename(Setting.temp_image_path, ".jpg")
            if os.path.getsize(Setting.temp_image_path) > 1024 * 1024 * 30:
                FileOperation.clear_folder_all(Setting.temp_image_path)
            if not image_path.parent.exists():
                Path.mkdir(Setting.temp_image_path, exist_ok=True)
            image_obj.save(image_path)

        self.core_control.after(0, lambda p=str(image_path.absolute()), o=image_obj: 
            self.core_control.preview_canvas1.append_result(p, o))
        self.__search_image(image_obj)

    @Decorator.send_task
    def search_image_by_text(self) -> None:
        text = self.core_control.search_entry.get().strip()
        self.core_control.after(0, self.core_control.preview_canvas1.clear_results)
        self.__search_image(text)

    def __search_image(self, input_data: Image.Image | str) -> None:
        if not self.core_control.setting.get_config("index", "search_dir"):
            messagebox.showinfo("提示", "请在设置选项卡索引至少一个目录！")
            return
        if not self._is_finish_search:
            return
        self._is_finish_search = False
        self._last_search_content = input_data
        # UI初始化操作转发到主线程
        if isinstance(input_data, str) and self._is_name_search:
            search_text = input_data
        else:
            search_text = ""
        self.core_control.after(0, self._prepare_search_ui, search_text)
        try:
            if isinstance(input_data, str) and self._is_name_search:
                results = self.core_control.search_tools.checkout_by_name(input_data)
            else:
                results = self.core_control.search_tools.checkout(input_data)
            try:
                first_result = next(results)
            except StopIteration:
                self._is_finish_search = True
                return
            all_extra_info: list[tuple[str, tuple]] = []
            for img_path, similarity in [first_result, *results]:
                if Path(img_path).exists() and self._is_in_selected_dirs(img_path):
                    extra_info = self.generate_extra_info(img_path, similarity)
                    all_extra_info.append((img_path, extra_info))
            
            # 在主线程中统一更新UI
            self.core_control.after(0, self._batch_append_results, all_extra_info)
        except Exception as e:
            logging.error(f"搜索时发生异常: {e}", exc_info=True)
            messagebox.showerror("错误", f"搜索失败：{e}")
        finally:
            self._is_finish_search = True

    def _prepare_search_ui(self, search_text: str) -> None:
        """在主线程中准备搜索UI（清除旧结果、设置搜索文本等）"""
        self.core_control.preview_view.set_search_text(search_text)
        self.core_control.preview_view.clear_results()
        self.core_control.sort_combo.set("相似度")

    def _batch_append_results(self, results: list[tuple[str, tuple]]) -> None:
        """在主线程中批量添加搜索结果到预览视图"""
        first_item = None
        for idx, (img_path, extra_info) in enumerate(results):
            item = self.core_control.preview_view.append_result(img_path, *extra_info)
            if idx == 0:
                first_item = item
        if first_item is not None:
            self.core_control.preview_view.selection_set(first_item)

    def generate_extra_info(self, image_path: str, similarity: float) -> tuple:
        image_path_obj = Path(image_path)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(image_path))
        content = (
            f"{os.path.getsize(image_path_obj) / 1024 / 1024:.2f}MB",
            mtime.strftime("%Y-%m-%d %H:%M:%S"),
            f"{similarity:.2f}%"
        )
        return content

    def set_preview_result_count(self, max_match_count: int) -> None:
        max_match_count = max(1, min(max_match_count, 100))
        self.core_control.setting.modity_config("index", "max_match_count", max_match_count)
        self.core_control.search_tools.update_max_match_count(max_match_count)
        self.core_control.result_count_entry.delete(0, tk.END)
        self.core_control.result_count_entry.insert(0, str(max_match_count))
        if self._last_search_content:
            self.__search_image(self._last_search_content)

    def apply_result_count_from_entry(self, event: tk.Event | None = None) -> None:
        raw_count = self.core_control.result_count_entry.get().strip()
        if not raw_count.isdigit():
            current_count = self.core_control.setting.get_config("index", "max_match_count") or 100
            self.core_control.result_count_entry.delete(0, tk.END)
            self.core_control.result_count_entry.insert(0, str(current_count))
            return
        self.set_preview_result_count(int(raw_count))

    def set_preview_mode(self, mode: Literal["detail_info", "medium_ico"]) -> None:
        self._switching_mode = True
        results = self.core_control.preview_view.get_show_results()
        current_selection = self.core_control.preview_view.selection()
        self.core_control.preview_view.destroy()
        self.core_control.setting.modity_config("function", "preview_mode", mode)
        if mode == "detail_info":
            self.core_control.preview_view = DetailListView(
                self.core_control.preview_container,
                {"大小": 100, "修改时间": 160, "相似度": 100}
            )
        else:
            self.core_control.preview_view = ThumbnailGridView(self.core_control.preview_container)
            if self._is_name_search and isinstance(self._last_search_content, str):
                self.core_control.preview_view.set_search_text(self._last_search_content)
        self.core_control.bind_event()
        for result in results:
            img_path, *extra_info = result
            self.core_control.preview_view.append_result(img_path, *extra_info)
        self.core_control.preview_view.selection_set(*current_selection)
        self._switching_mode = False

    def preview_found_image(self, event: tk.Event) -> None:
        if self._switching_mode:
            return
        selection = self.core_control.preview_view.selection()
        if not selection:
            return
        if self._preview_timer:
            self.core_control.after_cancel(self._preview_timer)
        self._preview_timer = self.core_control.after(100, lambda s=selection: self._do_preview_item(s))

    @Decorator.send_task
    def _do_preview_item(self, selection: tuple) -> None:
        try:
            first_item = selection[0]
            image_path = self.core_control.preview_view.item(first_item)[0]
            image_obj = ImageOperation.get_image_obj(image_path)
            if image_obj is not None:
                self.core_control.after(0, lambda p=image_path, o=image_obj: 
                    self.core_control.preview_canvas2.append_result(p, o))
        except KeyError:
            return



class IndexTableControl(object):
    def __init__(self, core_control: CoreControl) -> None:
        self.core_control = core_control
        self._is_updating: bool = False

    def update_index_tip(self) -> None:
        self.core_control.index_tip_label.config(
            text=f"当前索引图库({self.core_control.search_tools.valid_index_count}张图片)"
        )
        self.core_control.index_progress_bar.grid_remove()
        self.core_control.index_progress_label.config(text="")
        self._is_updating = False

    def add_search_dir(self, dir_path: str = "") -> None:
        if dir_path != "" and not Path(dir_path).is_dir():
            return
        if dir_path == "":
            dir_path = filedialog.askdirectory(title="选择索引文件夹")
            if not dir_path:
                return
        search_dirs: list = self.core_control.setting.get_config("index", "search_dir")
        if dir_path in search_dirs:
            messagebox.showinfo("提示", "新索引的目录已包含在当前索引目录中！")
            return
        for search_dir in search_dirs:
            if Path(dir_path).is_relative_to(search_dir):
                messagebox.showinfo("提示", "该文件夹是索引目录的子文件夹！")
                return
        search_dirs.append(dir_path)
        self.refresh_index_dataset_table()
        self.core_control.setting.save_settings()

    def rebuild_index(self) -> None:
        answer = messagebox.askyesno("提示", "重建索引极其耗时，\n您确定要进行重建吗？")
        if not answer:
            return
        try:
            self.core_control.search_tools.reset_index()
        except (FileNotFoundError, KeyError):
            pass
        self.sync_index()

    def refresh_index_dataset_table(self) -> None:
        tb = self.core_control.index_dataset_table
        all_items = tb.get_children()
        all_show_dir = {tb.item(node, 'values')[1] for node in all_items}
        for index_id, item in enumerate(all_items, 1):
            _, search_dir = tb.item(item, "values")
            tb.item(item, values=(index_id, search_dir))
        search_dirs = self.core_control.setting.get_config("index", "search_dir")
        all_items_count = len(all_items) + 1
        for search_dir in search_dirs:
            if search_dir not in all_show_dir:
                tb.insert("", tk.END, values=(all_items_count, search_dir))
                all_items_count += 1

    @Decorator.send_task
    @Decorator.redirect_output
    def sync_index(self, show_message: bool = True) -> None:
        self.core_control.delete_index_button.config(state=tk.DISABLED)
        self.core_control.rebuild_index_button.config(state=tk.DISABLED)
        self.core_control.update_index_button.config(
            text="终止索引更新", 
            command=lambda: self.core_control.search_tools.set_force_end_update(True)
        )
        self._is_updating = True
        self.__check_queue()
        self.core_control.search_tools.remove_nonexists()
        for image_dir in self.core_control.setting.get_config("index", "search_dir"):
            if Path(image_dir).exists():
                self.core_control.search_tools.update_index(
                    image_dir,
                    int(float(self.core_control.update_threads_count_scale.get()))
                )
        self.core_control.update_index_button.config(text="更新索引目录", command=self.sync_index)
        self.core_control.delete_index_button.config(state=tk.ACTIVE)
        self.core_control.rebuild_index_button.config(state=tk.ACTIVE)
        if show_message:
            messagebox.showinfo("提示", "索引更新完成！")
        self.core_control.after(1000, self.update_index_tip)
        self.core_control.search_tools.set_force_end_update(False)
        self._is_updating = False

    @Decorator.send_task
    @Decorator.redirect_output
    def delete_search_dir(self) -> None:
        selected = self.core_control.index_dataset_table.selection()
        if not selected:
            return
        answer = messagebox.askyesno("提示", "你确定要删除选中目录吗？")
        if not answer:
            return
        self._is_updating = True
        self.__check_queue()
        dirs_to_delete = []
        search_dir: list = self.core_control.setting.get_config("index", "search_dir")
        for item in selected:
            delete_search_dir = self.core_control.index_dataset_table.item(item, 'values')[1]
            dirs_to_delete.append(delete_search_dir)
            search_dir.remove(delete_search_dir)
            self.core_control.index_dataset_table.delete(item)
        self.refresh_index_dataset_table()
        for dir_path in dirs_to_delete:
            self.core_control.search_tools.remove_files_in_directory(dir_path)
        self.core_control.search_tools.remove_nonexists()
        self.core_control.setting.save_settings()
        self.core_control.after(1000, self.update_index_tip)

    def __check_queue(self) -> None:
        last_message = ""
        try:
            while True:
                last_message = Decorator.progress_queue.get_nowait()
        except Empty:
            pass
        if last_message:
            self._update_progress(last_message)
        if self._is_updating:
            self.core_control.after(200, self.__check_queue)

    def _update_progress(self, message: str) -> None:
        """解析进度消息并更新进度条和标签"""
        bar = self.core_control.index_progress_bar
        label = self.core_control.index_progress_label

        # 解析 "更新索引：X/Y (Z%)" 或 "清理失效索引：X/Y (Z%)" 格式
        match = re.search(r"[:：]\s*(\d+)\s*/\s*(\d+)\s*\((\d+\.?\d*)%\)", message)
        if match:
            done = int(match.group(1))
            total = int(match.group(2))
            percent = float(match.group(3))
            bar.grid()
            bar.config(maximum=total, value=done)
            label.config(text=message)
            return

        # 非进度消息（如 "扫描文件：..."、"扫描完成：..."）
        bar.grid()
        label.config(text=message)



class MenuControl(object):
    ACTIVE_BORDER_WIDTH = 6
    PHOTOSHOP_EXE_NAMES = ("Photoshop.exe", "photoshop.exe")
    PHOTOSHOP_COMMON_PATHS = tuple(
        Path("C:/Program Files/Adobe") / f"Adobe Photoshop {year}" / "Photoshop.exe"
        for year in range(2026, 2018, -1)
    )

    def __init__(self, core_control: CoreControl) -> None:
        self.core_control = core_control

    def __get_selected_result_files(self) -> list[Path]:
        selected_items = self.core_control.preview_view.selection()
        if not selected_items:
            messagebox.showinfo("提示", "请先选择搜索结果！")
            return []
        file_paths = [Path(self.core_control.preview_view.item(item)[0]) for item in selected_items]
        exists_files = [file_path for file_path in file_paths if file_path.exists()]
        if not exists_files:
            messagebox.showinfo("提示", "选中文件不存在！")
        return exists_files

    @Decorator.send_task
    def copy_selected_result_image(self) -> None:
        file_paths = self.__get_selected_result_files()
        if file_paths:
            FileOperation.copy_files(*file_paths)

    @Decorator.send_task
    def copy_selected_result_path(self) -> None:
        file_paths = self.__get_selected_result_files()
        if file_paths:
            FileOperation.copy_filepaths(*file_paths, tk=self.core_control)

    @Decorator.send_task
    def open_selected_result_with_photoshop(self) -> None:
        file_paths = self.__get_selected_result_files()
        if file_paths:
            self.open_with_photoshop(file_paths[0])

    @Decorator.send_task
    def copy_file_image_async(self, file_path: Path) -> None:
        if file_path.exists():
            FileOperation.copy_files(file_path)
        else:
            messagebox.showinfo("提示", "文件不存在！")

    @Decorator.send_task
    def copy_file_path_async(self, file_path: Path) -> None:
        if file_path.exists():
            FileOperation.copy_filepaths(file_path, tk=self.core_control)
        else:
            messagebox.showinfo("提示", "文件不存在！")

    @Decorator.send_task
    def open_file_with_photoshop_async(self, file_path: Path) -> None:
        if file_path.exists():
            self.open_with_photoshop(file_path)
        else:
            messagebox.showinfo("提示", "文件不存在！")

    def open_with_photoshop(self, file_path: Path) -> None:
        for exe_name in self.PHOTOSHOP_EXE_NAMES:
            try:
                subprocess.Popen([exe_name, str(file_path)])
                return
            except FileNotFoundError:
                pass
            except Exception as e:
                messagebox.showerror("错误", f"打开 Photoshop 失败：{e}")
                return
        for exe_path in self.PHOTOSHOP_COMMON_PATHS:
            if not exe_path.exists():
                continue
            try:
                subprocess.Popen([str(exe_path), str(file_path)])
                return
            except Exception as e:
                messagebox.showerror("错误", f"打开 Photoshop 失败：{e}")
                return
        messagebox.showinfo("提示", "未找到 Photoshop，请确认已安装或将 Photoshop 加入 PATH。")

    def __get_item_files(self, event: tk.Event, preview_widget: BasicImagePreviewView) -> list[Path]:
        selected_items = preview_widget.selection()
        current_selected_item = preview_widget.identify_item(event)
        if current_selected_item == "":
            return []
        if current_selected_item in selected_items:
            return [Path(preview_widget.item(item)[0]) for item in selected_items]
        preview_widget.selection_set(current_selected_item)
        return [Path(preview_widget.item(current_selected_item)[0])]
    
    @staticmethod
    def ask_for_filename(src_path: Path) -> str:
        return filedialog.asksaveasfilename(
            defaultextension=src_path.suffix,
            filetypes=[("图片文件", f"*{src_path.suffix}")],
            initialfile=src_path.stem
        )
    
    def create_right_click_menu(self, event: tk.Event, widget = None) -> None:
        if widget is None:
            widget = event.widget
        if not isinstance(widget, BasicImagePreviewView):
            return
        selected_files = self.__get_item_files(event, widget)
        if len(selected_files) == 0:
            return
        exists_files: list[Path] = [f for f in selected_files if f.exists()]
        if len(selected_files) == 1 and len(exists_files) == 1:
            file_path = selected_files[0]
            menu_items = [
                ("复制图片", lambda: FileOperation.copy_files(file_path)),
                ("复制路径", lambda: FileOperation.copy_filepaths(file_path, tk=self.core_control)),
                ("图片另存为", lambda: FileOperation.save_as(file_path, self.ask_for_filename(file_path), True)),
                ("打开图片", lambda: FileOperation.open_file(file_path)),
                ("打开文件夹", lambda: FileOperation.open_file(file_path, True))
            ]
        elif len(selected_files) > 1 and len(exists_files) != 0:
            menu_items = [
                ("复制图片", lambda: FileOperation.copy_files(*selected_files)),
                ("复制路径", lambda: FileOperation.copy_filepaths(*selected_files, tk=self.core_control)),
                ("图片另存为", lambda: FileOperation.save_to_dir(*selected_files, dest_dir=filedialog.askdirectory(), is_binary=True, inplace=False))
            ]
        else:
            messagebox.showinfo("提示", "选中文件不存在！")
            return
        menu = tk.Menu(tearoff=0, activeborderwidth=self.ACTIVE_BORDER_WIDTH)
        for label, cmd in menu_items:
            menu.add_command(label=label, command=cmd, compound=tk.LEFT)
        
        menu.post(event.x_root, event.y_root)
        menu.bind("<Unmap>", lambda e: menu.destroy())

    def double_click_open_file(self, event: tk.Event, widget = None) -> None:
        if widget is None:
            widget = event.widget
        if isinstance(widget, BasicImagePreviewView):
            selected_files = self.__get_item_files(event, widget)
        elif isinstance(widget, Treeview):
            selected_files = [Path(widget.item(widget.selection()[0], "values")[1])]
        else:
            selected_files = []
        if len(selected_files) == 0:
            return
        selected_file = selected_files[0]
        if not selected_file.exists():
            messagebox.showinfo("提示", "文件不存在！")
            return
        else:
            FileOperation.open_file(selected_file)

