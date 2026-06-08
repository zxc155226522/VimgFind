import tkinter as tk
from tkinter.ttk import Treeview, Scrollbar
from ttkbootstrap import Style, tooltip
from typing import Callable, Any
from collections import OrderedDict, namedtuple
import math
import hashlib
import os
from pathlib import Path


from PIL import Image, ImageTk, ImageOps, UnidentifiedImageError


from utils import ImageLoader, FileOperation
from setting import WinInfo


ThemeColor = namedtuple("ThemeColor", ["primary", "fg", "selectbg", "inputbg"])
class BasicImagePreviewView(object):
    def __init__(self, parent: tk.Widget) -> None:
        self.parent = parent
        self._results: OrderedDict[str, tuple] = OrderedDict(dict())
        self.theme_color = self._get_theme_colors()

    def _generate_unique_path_item(self, path: str) -> str:
        norm_path = os.path.normpath(path)
        path_item = hashlib.md5(norm_path.encode()).hexdigest()[:16]
        while path_item in self._results:
            path_item += "#"
        return path_item

    def _get_theme_colors(self) -> ThemeColor:
        """
        ttkbootstrap的style.colors是一个类属性，但它的返回类型错误地标注成了列表，
        导致正常访问它的属性IDE会警告，这里多包一层，只是为了获取类型注解
        """
        style = Style()
        style_color = style.colors
        color_attr = [getattr(style_color, field) for field in ThemeColor._fields]
        return ThemeColor(*color_attr)

    def _change_theme(self) -> None:
        self.theme_color = self._get_theme_colors()

    def append_result(self, image_path: str, *extra_info: Any, **kwargs: Any) -> str:
        return self._generate_unique_path_item(image_path)

    def get_show_results(self) -> list[tuple]:
        return list(self._results.values())

    def clear_results(self) -> None:
        pass

    def selection(self) -> tuple[str, ...]:
        return ()

    def selection_set(self, *items: str) -> None:
        pass

    def identify_item(self, event: tk.Event) -> str:
        return ""

    def item(self, item) -> tuple:
        return self._results[item]

    def bind(self, sequence: str, func: Callable) -> None:
        pass

    def set_search_text(self, text: str) -> None:
        pass

    def destroy(self) -> None:
        pass



class PreviewCanvasView(BasicImagePreviewView):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self._canvas = self._create_canvas(parent)
        self._tooltip = tooltip.ToolTip(self._canvas, text="没有文件", delay=500)
        self._original_image: Image.Image | None = None
        self._scale = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._zoom_text_id: int | None = None
        self._zoom_text_timer = ""
        self._bind_zoom_events()

    def _create_canvas(self, parent) -> tk.Canvas:
        canvas = tk.Canvas(parent, highlightthickness=0, cursor="hand2")
        canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        return canvas

    def _bind_zoom_events(self) -> None:
        self._canvas.bind("<MouseWheel>", self._on_zoom)
        self._canvas.bind("<Button-4>", self._on_zoom)
        self._canvas.bind("<Button-5>", self._on_zoom)
        self._canvas.bind("<ButtonPress-1>", self._on_drag_start, add="+")
        self._canvas.bind("<B1-Motion>", self._on_drag_move, add="+")
        self._canvas.bind("<ButtonRelease-1>", self._on_drag_end, add="+")
        self._canvas.bind("<Double-Button-1>", self._on_reset_zoom)

    def _on_zoom(self, event: tk.Event) -> None:
        if self._original_image is None:
            return
        if event.delta:
            delta = 1.1 if event.delta > 0 else 1 / 1.1
        elif event.num == 4:
            delta = 1.1
        elif event.num == 5:
            delta = 1 / 1.1
        else:
            return

        new_scale = self._scale * delta
        if new_scale < 0.1 or new_scale > 5.0:
            return

        cx = self._canvas.canvasx(event.x) - self._canvas.winfo_width() // 2
        cy = self._canvas.canvasy(event.y) - self._canvas.winfo_height() // 2

        self._offset_x = int(cx - (cx - self._offset_x) * delta)
        self._offset_y = int(cy - (cy - self._offset_y) * delta)
        self._scale = new_scale
        self._redraw()

    def _on_drag_start(self, event: tk.Event) -> None:
        if self._original_image is not None:
            self._drag_start_x = event.x
            self._drag_start_y = event.y

    def _on_drag_move(self, event: tk.Event) -> None:
        if self._original_image is None:
            return
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        self._offset_x += dx
        self._offset_y += dy
        self._redraw()

    def _on_drag_end(self, event: tk.Event) -> None:
        pass

    def _on_reset_zoom(self, event: tk.Event) -> None:
        if self._original_image is not None:
            self._scale = 1.0
            self._offset_x = 0
            self._offset_y = 0
            self._redraw()

    def _redraw(self) -> None:
        if self._original_image is None:
            return
        canvas_w = max(self._canvas.winfo_width(), 100)
        canvas_h = max(self._canvas.winfo_height(), 80)
        img_w, img_h = self._original_image.size
        fit_scale = min(canvas_w / img_w, canvas_h / img_h)
        scaled_w = max(1, int(img_w * fit_scale * self._scale))
        scaled_h = max(1, int(img_h * fit_scale * self._scale))

        resized = self._original_image.resize((scaled_w, scaled_h), Image.Resampling.BICUBIC)
        imgtk = ImageTk.PhotoImage(resized)

        self._canvas.delete(tk.ALL)
        cx = canvas_w // 2 + self._offset_x
        cy = canvas_h // 2 + self._offset_y
        self._canvas.create_image(cx, cy, anchor=tk.CENTER, image=imgtk)

        if self._scale != 1.0:
            self._zoom_text_id = self._canvas.create_text(
                10, 10, anchor=tk.NW,
                text=f"{int(self._scale * 100)}%",
                fill="white",
                font=("微软雅黑", 10, "bold")
            )
            self._schedule_hide_zoom_text()
        elif self._zoom_text_id is not None:
            self._zoom_text_id = None

        for iid in list(self._results.keys()):
            self._results[iid] = (self._results[iid][0], imgtk)

    def _schedule_hide_zoom_text(self) -> None:
        if self._zoom_text_timer:
            self.parent.after_cancel(self._zoom_text_timer)
        self._zoom_text_timer = self.parent.after(1500, self._hide_zoom_text)

    def _hide_zoom_text(self) -> None:
        if self._zoom_text_id is not None:
            self._canvas.delete(self._zoom_text_id)
            self._zoom_text_id = None
        self._zoom_text_timer = ""

    def append_result(self, image_path: str, image_obj: Image.Image) -> str:
        iid = self._generate_unique_path_item(image_path)
        try:
            img: Image.Image = ImageOps.exif_transpose(image_obj)
        except UnidentifiedImageError:
            return ""
        self.clear_results()
        self._original_image = img
        self._scale = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self._results[iid] = (image_path, None)
        self._tooltip.text = image_path
        self._redraw()
        return iid
    
    def clear_results(self) -> None:
        self._results.clear()
        self._original_image = None
        self._scale = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self._zoom_text_id = None
        self._canvas.delete(tk.ALL)
        self._tooltip.text = "没有文件"

    def selection(self) -> tuple[str, ...]:
        return tuple(self._results.keys())
    
    def identify_item(self, event: tk.Event) -> str:
        return list(self._results.keys())[0] if self._results else ""

    def bind(self, sequence: str, func: Callable) -> None:
        self._canvas.bind(sequence, func)

    def destroy(self) -> None:
        self._results.clear()
        self._original_image = None
        if self._zoom_text_timer:
            self.parent.after_cancel(self._zoom_text_timer)
        self._canvas.destroy()



class DetailListView(BasicImagePreviewView):
    THUMB_SIZE = 40
    THUMBNAIL_FILE_SIZE_LIMIT = 3 * 1024 * 1024

    def __init__(self, parent: tk.Widget, extra_columns: dict[str, int]) -> None:
        super().__init__(parent)
        self._is_destroy = False
        self._thumbnail_cache: dict[str, ImageTk.PhotoImage] = {}
        self._create_treeview(extra_columns)
        self.parent.after(50, self._create_scrollbar)
        
    def _create_treeview(self, extra_columns: dict[str, int]) -> None:
        columns = {"名称":160, **extra_columns}
        self.__treeview = Treeview(self.parent, show="tree headings", columns=list(columns))
        self.__treeview.heading("#0", text="")
        self.__treeview.column("#0", width=self.THUMB_SIZE + 10, anchor='center', stretch=False, minwidth=self.THUMB_SIZE + 10)
        for text, width in columns.items():
            self.__treeview.heading(text, text=text, anchor='center')
            self.__treeview.column(text, anchor='center', width=width, stretch=True)
        self.__treeview.place(relx=0, rely=0, relwidth=1, relheight=1)
        for column in self.__treeview["columns"]:
            self.__treeview.heading(column, command=lambda column=column: self._sort_column(column, False))

    def _create_scrollbar(self) -> None:
        if self._is_destroy:
            return
        self.__scrollbar = Scrollbar(self.__treeview, orient="vertical", cursor="hand2")
        self.__scrollbar.pack(fill="both", side="right", padx=2, pady=2)
        self.__scrollbar.config(command=self.__treeview.yview)
        self.__treeview.configure(yscrollcommand=self.__scrollbar.set)
    
    def _get_colomn_idx(self, column) -> int:
        columns: tuple = self.__treeview["columns"]
        return columns.index(column)

    def _sort_column(self, col: str, reverse: bool) -> None:
        data = [(self.__treeview.set(k, col), k) for k in self.__treeview.get_children("")]
        if col == "相似度" or col == "大小":
            data.sort(key = lambda x: f"{x[0]:0>10}", reverse=reverse)
        else:
            data.sort(reverse=reverse)
        for index, (_, k) in enumerate(data):
            self.__treeview.move(k, "", index)
        self.__treeview.heading(col, command=lambda: self._sort_column(col, not reverse))

    def append_result(self, image_path: str, *extra_info: str | int) -> str:
        iid = self._generate_unique_path_item(image_path)
        content = (os.path.basename(image_path), *extra_info)
        self._results[iid] = (image_path, *extra_info)
        tree_iid = self.__treeview.insert('', tk.END, values=content, iid=iid, text="")
        self._load_thumbnail_async(image_path, iid)
        return tree_iid

    def _load_thumbnail_async(self, image_path: str, iid: str) -> None:
        def _do_load() -> None:
            if self._is_destroy:
                return
            try:
                img = Image.open(image_path)
                if os.path.getsize(image_path) > self.THUMBNAIL_FILE_SIZE_LIMIT:
                    img.thumbnail((self.THUMB_SIZE, self.THUMB_SIZE))
                img = ImageOps.exif_transpose(img)
                photo = ImageTk.PhotoImage(img)
                self._thumbnail_cache[iid] = photo
                self.parent.after(0, lambda: self._set_thumbnail(iid, photo))
            except Exception:
                pass
        import threading
        threading.Thread(target=_do_load, daemon=True).start()

    def _set_thumbnail(self, iid: str, photo: ImageTk.PhotoImage) -> None:
        if self._is_destroy:
            return
        try:
            if self.__treeview.exists(iid):
                self.__treeview.item(iid, image=photo)
        except tk.TclError:
            pass
            
    def clear_results(self) -> None:
        if self._is_destroy:
            return
        self._results.clear()
        self._thumbnail_cache.clear()
        self.__treeview.delete(*self.__treeview.get_children())
    
    def selection(self) -> tuple[str, ...]:
        return self.__treeview.selection()
    
    def selection_set(self, *items: str) -> None:
        if not items:
            return
        if items[0] == tk.ALL:
            self.__treeview.selection_set(self.__treeview.get_children(""))
        else:
            self.__treeview.selection_set(items)
    
    def identify_item(self, event: tk.Event) -> str:
        return self.__treeview.identify_row(event.y)

    def bind(self, sequence: str, func: Callable) -> None:
        if sequence == "<<ItemviewSelect>>":
            sequence = "<<TreeviewSelect>>"
        self.__treeview.bind(sequence, func)

    def destroy(self) -> None:
        self._is_destroy = True
        try:
            self.__scrollbar.destroy()
        except Exception:
            pass
        try:
            self.__treeview.destroy()
        except Exception:
            pass



class ThumbnailGridView(BasicImagePreviewView):
    """
    缩略图网格式绘制类，不提供指定位置插入元素及删除操作
    """
    THUMBNAIL_SIZE: int = WinInfo.TkS(150)
    MARGIN: int = WinInfo.TkS(10)
    FONT_HEGIHT: int = WinInfo.TkS(48)
    TEXT_BOTTOM_PAD: int = WinInfo.TkS(8)
    BUTTON_HEIGHT: int = WinInfo.TkS(30)
    BUTTON_GAP: int = WinInfo.TkS(4)
    PRELOAD_ROWS: int = 3
    MIN_THUMB_SIZE: int = 80
    MAX_THUMB_SIZE: int = 400
    THUMB_STEP: int = 20
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self._create_canvas()
        self.parent.after(50, self._create_scrollbar)

        self._image_loader = ImageLoader()
        self._loading_tasks: set[str] = set()
        self._visible_image_data: dict[str, dict] = {}

        # 记录画布的id项以及索引位置
        self._tooltip = None
        self._canvas_items: dict[str, dict[str, int]] = {}
        self._visible_items: set[str] = set()
        self._selected_items: set[str] = set()
        self._button_areas: dict[str, dict[str, tuple]] = {}
        self._hovered_button: tuple[str, str] | None = None
        self.copy_image_callback: Callable[[Path], None] | None = None
        self.copy_path_callback: Callable[[Path], None] | None = None
        self.open_ps_callback: Callable[[Path], None] | None = None
        self._search_text: str = ""
        self._highlight_color: str = "#FFD700"
        
        # 定时器
        self._scroll_timer = ""
        self._scrollbar_drag_timer = ""
        self._check_timer = ""

        self._cols = 0
        self._h_gap = self.MARGIN
        self._target_thumb_size = self.THUMBNAIL_SIZE
        self._is_destroy = False
        self._is_scrollbar_dragging = False
        
        self._bind_event()
        self._check_results()
    
    def _create_canvas(self) -> None:
        self._canvas = tk.Canvas(self.parent)
        self._canvas.grid(row=0, column=0, sticky=tk.NSEW, )
        self.parent.grid_rowconfigure(0, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)
        self._canvas.grid_columnconfigure(0, weight=1)
        self._canvas.grid_rowconfigure(0, weight=1)
        self._canvas.configure(
            takefocus=1,
            background=self.theme_color.inputbg,
            highlightthickness=1, 
            highlightbackground=self.theme_color.primary,
            highlightcolor=self.theme_color.primary
        )
        self._canvas.update()

    def _create_scrollbar(self) -> None:
        # 滚动条的初始化格外慢，因此将将其独立出来
        self._scrollbar = Scrollbar(self._canvas, orient=tk.VERTICAL, cursor="hand2")
        self._scrollbar.grid(row=0, column=1, sticky=tk.NS, padx=2, pady=2)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.config(command=self._on_scrollbar_scroll)
        self._scrollbar.bind("<B1-Motion>", self._on_scrollbar_drag)
        self._scrollbar.bind("<ButtonRelease-1>", self._on_scrollbar_release)

    def _bind_event(self) -> None:
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Button-4>", self._on_mousewheel)  # Linux
        self._canvas.bind("<Button-5>", self._on_mousewheel)  # Linux
        self._canvas.bind("<Button-1>", self._on_canvas_click)
        self._canvas.bind("<ButtonPress-1>", self._on_action_press, add="+")
        self._canvas.bind("<ButtonRelease-1>", self._on_action_release, add="+")
        self._canvas.bind("<Motion>", self._on_action_motion, add="+")
        self._canvas.bind("<KeyPress>", self._on_keyboard_click)
        self._canvas.bind("<<ThemeChanged>>", lambda e: self._change_theme())
        self._canvas.bind("<Enter>", lambda e: self._canvas.config(highlightbackground=self.theme_color.primary))
        self._canvas.bind("<Leave>", lambda e: self._canvas.config(highlightbackground=self.theme_color.selectbg))
        self._canvas.bind("<FocusIn>", lambda e: self._canvas.config(highlightthickness=2))
        self._canvas.bind("<FocusOut>", lambda e: self._canvas.config(highlightthickness=1))

    def _change_theme(self) -> None:
        super()._change_theme()
        for item_id in self._canvas.find_all():
            tags = self._canvas.gettags(item_id)
            if self._canvas.type(item_id) == "text":
                if "search_highlight" in tags:
                    self._canvas.itemconfig(item_id, fill=self._highlight_color)
                else:
                    self._canvas.itemconfig(item_id, fill=self.theme_color.fg)
            elif self._canvas.type(item_id) == "rectangle":
                if any(tag.startswith("action:") for tag in tags):
                    self._canvas.itemconfig(item_id, fill=self.theme_color.inputbg, outline=self.theme_color.primary)
                else:
                    self._canvas.itemconfig(item_id, fill=self.theme_color.selectbg)
        self._canvas.configure(
            background=self.theme_color.inputbg,
            highlightbackground=self.theme_color.primary,
            highlightcolor=self.theme_color.primary,
            highlightthickness=1
        )
        
    def _on_scrollbar_scroll(self, *args) -> None:
        if len(args) == 2:
            self._canvas.yview(*args)
        else:
            self._canvas.xview(*args)
        self._schedule_load()
    
    def _on_scrollbar_drag(self, event: tk.Event) -> None:
        def _on_scrollbar_drag_update() -> None:
            if not self._is_scrollbar_dragging:
                self._scrollbar_drag_timer = None
                return
            self._load_visible_images()
            if self._is_scrollbar_dragging:
                self._scrollbar_drag_timer = self.parent.after(50, _on_scrollbar_drag_update)
        self._is_scrollbar_dragging = True
        if self._scrollbar_drag_timer:
            self.parent.after_cancel(self._scrollbar_drag_timer)
        self._scrollbar_drag_timer = self.parent.after(50, _on_scrollbar_drag_update)
    
    def _on_scrollbar_release(self, event: tk.Event) -> None:
        self._is_scrollbar_dragging = False
        if self._scrollbar_drag_timer:
            self.parent.after_cancel(self._scrollbar_drag_timer)
            self._scrollbar_drag_timer = None
        self._schedule_load()
    
    def _on_mousewheel(self, event: tk.Event) -> None:
        # 普通滚动
        if event.delta:
            delta = int(-1 * (event.delta / 120))
            self._canvas.yview_scroll(delta, "units")
        # Linux
        elif event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        self._schedule_load()

    def _on_keyboard_click(self, event: tk.Event) -> None:
        monitor_key = ["Left", "KP_Left", "Right", "KP_Right", "Up", "KP_Up", "Down", "KP_Down"]
        if event.keysym not in monitor_key:
            return
        items_list = list(self._results.keys())
        if not items_list or self._cols == 0:
            return
        target_index = -1
        max_index = len(items_list) - 1
        current_index = max(self._get_item_index(item) for item in self._selected_items)
        if event.keysym in ("Left", "KP_Left"):
            target_index = max(0, current_index - 1)
        elif event.keysym in ("Right", "KP_Right"):
            target_index = min(max_index, current_index + 1)
        elif event.keysym in ("Up", "KP_Up"):
            target_index = current_index if current_index - self._cols < 0 else current_index - self._cols
        elif event.keysym in ("Down", "KP_Down"):
            target_index = current_index if current_index + self._cols > max_index else current_index + self._cols
        if target_index == current_index:
            return
        target_item = items_list[target_index]
        self.selection_set(target_item)
        self._scroll_to_item(target_item, event)

    def _scroll_to_item(self, item: str, event: tk.Event) -> None:
        _, y, _, item_y2 = self._get_item_bounds(item)
        item_y1 = y
        canvas_y1 = self._canvas.canvasy(0)
        canvas_y2 = canvas_y1 + self._canvas.winfo_height()
        total_height = self._canvas.bbox(tk.ALL)[3] if self._canvas.bbox(tk.ALL) else 1
        if item_y2 > canvas_y2:
            self._canvas.yview_moveto((item_y2 - self._canvas.winfo_height()) / total_height)
        elif item_y1 < canvas_y1:
            self._canvas.yview_moveto(item_y1 / total_height)
        self._create_action_buttons(item)
        self._on_scrollbar_release(event)

    def _on_canvas_configure(self, event) -> None:
        def delayed_resize() -> None:
            self._update_layout()
            self._load_visible_images()
            self._scroll_timer = None
        if self._scroll_timer:
            self.parent.after_cancel(self._scroll_timer)
        self._scroll_timer = self.parent.after(100, delayed_resize)

    def _on_canvas_click(self, event: tk.Event) -> None:
        self._canvas.focus_set()
        clicked_action = self._identify_action(event)
        if clicked_action:
            item, action = clicked_action
            self._run_item_action(item, action)
            return
        clicked_item = self.identify_item(event)
        if not clicked_item:
            return
        state = int(event.state)
        ctrl_pressed = (state & 0x0004) != 0
        shift_pressed = (state & 0x0001) != 0

        if ctrl_pressed:
            if clicked_item in self._selected_items:
                self._selected_items.remove(clicked_item)
                self._set_item_selected(clicked_item, False)
            else:
                self._selected_items.add(clicked_item)
                self._set_item_selected(clicked_item, True)
        elif shift_pressed:
            if not self._selected_items:
                self._selected_items.add(clicked_item)
                self._set_item_selected(clicked_item, True)
            else:
                clicked_index = self._get_item_index(clicked_item)
                if clicked_index == -1:
                    return
                closest_selected_item = closest_selected_index = None
                closest_distance = float('inf')
                for selected_item in self._selected_items:
                    selected_index = self._get_item_index(selected_item)
                    if selected_index == -1:
                        continue
                    curr_distance = abs(selected_index - clicked_index)
                    if curr_distance < closest_distance:
                        closest_distance = curr_distance
                        closest_selected_item = selected_item
                        closest_selected_index = selected_index
                if closest_selected_item is None or closest_selected_index is None:
                    self.selection_set(clicked_item)
                    return
                start_index = min(closest_selected_index, clicked_index)
                end_index = max(closest_selected_index, clicked_index)
                range_selected_items = set()
                for index, item in enumerate(self._results):
                    if start_index <= index <= end_index:
                        range_selected_items.add(item)
                self.selection_set(*range_selected_items)
        else:
            self.selection_set(clicked_item)
            self._canvas.event_generate("<<ItemviewSelect>>")

    def _schedule_load(self) -> None:
        if self._scroll_timer:
            self.parent.after_cancel(self._scroll_timer)
        self._scroll_timer = self.parent.after(100, self._load_visible_images)
    
    def _check_results(self) -> None:
        if self._is_destroy:
            return
        results = self._image_loader.get_results()
        for result in results:
            item = result.item
            self._loading_tasks.discard(item)
            if item not in self._results:
                continue
            self._visible_image_data[item] = {'photo': result.photo, 'size': result.size, 'error': result.error}
            if item in self._canvas_items:
                self._create_canvas_item(item)
        self._check_timer = self.parent.after(100, self._check_results)

    def _cancel_timer(self) -> None:
        if self._scroll_timer:
            self.parent.after_cancel(self._scroll_timer)
        if self._scrollbar_drag_timer:
            self.parent.after_cancel(self._scrollbar_drag_timer)
        if self._check_timer:
            self.parent.after_cancel(self._check_timer)

# 分割线------------------------------------------------------------------------------------------------

    def _get_item_index(self, item: str) -> int:
        if item not in self._canvas_items:
            index = next((idx for idx, key in enumerate(self._results) if key == item), -1)
        else:
            index = self._canvas_items[item]["pos_index"]
        return index

    def _get_item_height(self) -> int:
        return self.THUMBNAIL_SIZE + self.MARGIN + self.FONT_HEGIHT + self.TEXT_BOTTOM_PAD + self.BUTTON_GAP + self.BUTTON_HEIGHT

    def _get_text_y(self, item_y: int) -> int:
        return item_y + self.THUMBNAIL_SIZE + self.MARGIN // 2

    def _get_button_y(self, item_y: int) -> int:
        return self._get_text_y(item_y) + self.FONT_HEGIHT + self.TEXT_BOTTOM_PAD

    def _get_item_bounds(self, item: str) -> tuple[int, int, int, int]:
        x, y = self._get_item_position(item)
        return (x, y, x + self.THUMBNAIL_SIZE, y + self._get_item_height())

    def _create_placeholder(self, item: str) -> None:
        x, y = self._get_item_position(item)
        filename = os.path.basename(self._results[item][0])
        placeholder_id = self._canvas.create_text(
            x + self.THUMBNAIL_SIZE // 2, y + self.THUMBNAIL_SIZE // 2,
            text=f"图片加载中...", fill=self.theme_color.fg
        )
        text_fill = self._highlight_color if self._search_text and self._search_text.lower() in filename.lower() else self.theme_color.fg
        text_tags = ("filename_text", "copy_filename", f"item:{item}")
        if self._search_text and self._search_text.lower() in filename.lower():
            text_tags += ("search_highlight",)
        image_info_id = self._canvas.create_text(
            x + self.THUMBNAIL_SIZE // 2, 
            self._get_text_y(y),
            text=filename, fill=text_fill, tags=text_tags,
            anchor=tk.N, width=self.THUMBNAIL_SIZE
        )
        self._canvas.tag_bind(image_info_id, "<ButtonPress-1>", lambda e, it=item: self._on_filename_drag_start(e, it))
        self._canvas.tag_bind(image_info_id, "<ButtonRelease-1>", lambda e, it=item: self._on_filename_drag_end(e, it))
        self._canvas.tag_bind(image_info_id, "<Enter>", lambda e: self._canvas.config(cursor="hand2"))
        self._canvas.tag_bind(image_info_id, "<Leave>", lambda e: self._canvas.config(cursor=""))
        self._canvas_items[item] = {
            "placeholder_id": placeholder_id, 
            "image_info_id": image_info_id,
            "action_ids": [],
            "pos_index": len(self._results) - 1
        }
        self._create_action_buttons(item)

    def _create_canvas_item(self, item: str) -> None:
        if item not in self._visible_image_data or item not in self._canvas_items:
            return
        
        self._create_action_buttons(item)
        image_data = self._visible_image_data[item]
        canvas_item = self._canvas_items[item]
        x, y = self._get_item_position(item)
        
        self._canvas.delete(canvas_item["placeholder_id"])
        canvas_item["placeholder_id"] = ""

        filename = os.path.basename(self._results[item][0])
        width, height = image_data["size"]
        
        tip_info = f"{filename}\n{width} × {height}"
        text_fill = self._highlight_color if self._search_text and self._search_text.lower() in filename.lower() else self.theme_color.fg
        self._canvas.itemconfig(canvas_item["image_info_id"], text=tip_info, fill=text_fill, width=self.THUMBNAIL_SIZE)
        if self._search_text and self._search_text.lower() in filename.lower():
            self._canvas.itemconfig(canvas_item["image_info_id"], tags=("filename_text", "copy_filename", f"item:{item}", "search_highlight"))
        
        if image_data['photo'] is not None:
            if "image_id" not in canvas_item:
                image_id = self._canvas.create_image(
                    x + self.THUMBNAIL_SIZE // 2, 
                    y + self.THUMBNAIL_SIZE // 2, 
                    image=image_data['photo']
                )
                canvas_item["image_id"] = image_id
            else:
                self._canvas.itemconfig(canvas_item["image_id"], image=image_data['photo'])
        else:
            self._canvas.itemconfig(canvas_item["placeholder_id"], text=f"{image_data.get('error', '加载失败')[:10]}")

    def _on_action_motion(self, event: tk.Event) -> None:
        """通过 Motion 事件检测鼠标是否悬停在按钮上，更新 hover 状态"""
        cx = self._canvas.canvasx(event.x)
        cy = self._canvas.canvasy(event.y)
        new_hover: tuple[str, str] | None = None
        for item, actions in self._button_areas.items():
            if item not in self._canvas_items:
                continue
            for action, (x1, y1, x2, y2) in actions.items():
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    new_hover = (item, action)
                    break
            if new_hover:
                break

        old_hover = self._hovered_button
        if new_hover == old_hover:
            return

        # 取消旧按钮的 hover
        if old_hover is not None:
            old_item, old_action = old_hover
            if old_item in self._canvas_items:
                old_rect_tag = f"action_rect:{old_action}:{old_item}"
                old_text_tag = f"action_text:{old_action}:{old_item}"
                self._canvas.itemconfig(old_rect_tag, fill=self.theme_color.inputbg, outline=self.theme_color.primary)
                self._canvas.itemconfig(old_text_tag, fill=self.theme_color.fg)

        # 设置新按钮的 hover
        if new_hover is not None:
            new_item, new_action = new_hover
            new_rect_tag = f"action_rect:{new_action}:{new_item}"
            new_text_tag = f"action_text:{new_action}:{new_item}"
            self._canvas.itemconfig(new_rect_tag, fill=self.theme_color.primary, outline=self.theme_color.primary)
            self._canvas.itemconfig(new_text_tag, fill="white")
            self._canvas.config(cursor="hand2")
        else:
            self._canvas.config(cursor="")

        self._hovered_button = new_hover

    def _on_action_press(self, event: tk.Event) -> None:
        """鼠标按下时显示按压状态"""
        if self._hovered_button is None:
            return
        item, action = self._hovered_button
        if item not in self._canvas_items:
            return
        rect_tag = f"action_rect:{action}:{item}"
        self._canvas.itemconfig(rect_tag, fill=self.theme_color.selectbg)

    def _on_action_release(self, event: tk.Event) -> None:
        """鼠标松开时恢复 hover 状态"""
        if self._hovered_button is None:
            return
        item, action = self._hovered_button
        if item not in self._canvas_items:
            return
        rect_tag = f"action_rect:{action}:{item}"
        self._canvas.itemconfig(rect_tag, fill=self.theme_color.primary)

    def _on_filename_drag_start(self, event: tk.Event, item: str) -> None:
        self._filename_drag_item = item

    def _on_filename_drag_end(self, event: tk.Event, item: str) -> None:
        if getattr(self, '_filename_drag_item', '') == item:
            self._copy_filename_to_clipboard(item)
            self._filename_drag_item = ''

    def _copy_filename_to_clipboard(self, item: str) -> None:
        if item not in self._results:
            return
        file_path = self._results[item][0]
        self._canvas.clipboard_clear()
        self._canvas.clipboard_append(file_path)
        self._show_copy_tooltip(item)

    def _show_copy_tooltip(self, item: str) -> None:
        if item not in self._canvas_items:
            return
        x, y = self._get_item_position(item)
        tip_x = x + self.THUMBNAIL_SIZE // 2
        tip_y = self._get_button_y(y) + self.BUTTON_HEIGHT + self.BUTTON_GAP + 12
        tooltip_id = self._canvas.create_text(
            tip_x, tip_y, text="已复制", fill="white",
            font=("微软雅黑", 9)
        )
        bbox = self._canvas.bbox(tooltip_id)
        if bbox:
            bg_id = self._canvas.create_rectangle(
                bbox[0] - 4, bbox[1] - 2, bbox[2] + 4, bbox[3] + 2,
                fill=self.theme_color.primary, outline=""
            )
            self._canvas.tag_lower(bg_id, tooltip_id)
        self.parent.after(1200, lambda tid=tooltip_id, bid=bg_id if bbox else None: (
            self._canvas.delete(tid),
            bid is not None and self._canvas.delete(bid)
        ))

    def _create_action_buttons(self, item: str) -> None:
        if item not in self._canvas_items:
            return
        canvas_item = self._canvas_items[item]
        for canvas_id in canvas_item.get("action_ids", []):
            self._canvas.delete(canvas_id)
        x, y = self._get_item_position(item)
        labels = (("copy_image", "复制图"), ("copy_path", "路径"), ("open_ps", "PS"))
        total_gap = self.BUTTON_GAP * (len(labels) - 1)
        button_width = (self.THUMBNAIL_SIZE - total_gap) // len(labels)
        button_y1 = self._get_button_y(y)
        button_y2 = button_y1 + self.BUTTON_HEIGHT
        action_ids = []
        item_areas: dict[str, tuple] = {}
        for index, (action, label) in enumerate(labels):
            button_x1 = x + index * (button_width + self.BUTTON_GAP)
            button_x2 = button_x1 + button_width
            action_tag = f"action:{action}"
            rect_tag = f"action_rect:{action}:{item}"
            text_tag = f"action_text:{action}:{item}"
            item_tag = f"item:{item}"
            rect_id = self._canvas.create_rectangle(
                button_x1, button_y1, button_x2, button_y2,
                outline=self.theme_color.primary,
                fill=self.theme_color.inputbg,
                width=1,
                tags=(action_tag, rect_tag, item_tag)
            )
            text_id = self._canvas.create_text(
                (button_x1 + button_x2) // 2,
                (button_y1 + button_y2) // 2,
                text=label,
                fill=self.theme_color.fg,
                font=("微软雅黑", 9),
                tags=(action_tag, text_tag, item_tag)
            )
            action_ids.extend((rect_id, text_id))
            item_areas[action] = (button_x1, button_y1, button_x2, button_y2)
        canvas_item["action_ids"] = action_ids
        border_id = canvas_item.get("border_id", "")
        if border_id:
            for action_id in action_ids:
                self._canvas.tag_raise(action_id, border_id)
        self._button_areas[item] = item_areas

    def _identify_action(self, event: tk.Event) -> tuple[str, str] | None:
        canvas_id = self._canvas.find_withtag(tk.CURRENT)
        if not canvas_id:
            return None
        tags = self._canvas.gettags(canvas_id[0])
        action = next((tag.split(":", 1)[1] for tag in tags if tag.startswith("action:")), None)
        item = next((tag.split(":", 1)[1] for tag in tags if tag.startswith("item:")), None)
        if action is not None and item in self._results:
            return item, action
        return None

    def _run_item_action(self, item: str, action: str) -> None:
        file_path = Path(self._results[item][0])
        callback = {
            "copy_image": self.copy_image_callback,
            "copy_path": self.copy_path_callback,
            "open_ps": self.open_ps_callback,
        }.get(action)
        if callback is not None:
            callback(file_path)

    def _set_item_selected(self, item: str, selected: bool) -> None:
        canvas_item = self._canvas_items[item]
        if not selected:
            border_id = canvas_item.get("border_id", "")
            if border_id:
                self._canvas.delete(border_id)
                canvas_item.pop("border_id")
            return
        if canvas_item.get("border_id", ""):
            return
        x, y, x2, y2 = self._get_item_bounds(item)
        border_id = self._canvas.create_rectangle(
            x - 4, y - 4, x2 + 4, y2 + 4,
            fill=self.theme_color.selectbg
        )
        canvas_item["border_id"] = border_id
        self._canvas.tag_lower(border_id)
        for action_id in canvas_item.get("action_ids", []):
            self._canvas.tag_raise(action_id, border_id)

    def _update_layout(self) -> None:
        canvas_width = self._canvas.winfo_width()
        canvas_height = self._canvas.winfo_height()

        old_thumb_size = self.THUMBNAIL_SIZE
        # 固定5列，缩略图大小根据窗口宽度自动计算
        available_width = max(canvas_width - self.MARGIN * 2 - 20, self.MIN_THUMB_SIZE)
        self._cols = 5
        self._h_gap = self.MARGIN
        self.THUMBNAIL_SIZE = max(
            self.MIN_THUMB_SIZE,
            min(self.MAX_THUMB_SIZE, (available_width - (self._cols - 1) * self._h_gap) // self._cols)
        )
        size_changed = old_thumb_size != self.THUMBNAIL_SIZE

        if size_changed and old_thumb_size != 0:
            for item, canvas_item in self._canvas_items.items():
                x, y = self._get_item_position(item)
                image_id = canvas_item.get("image_id", "")
                if image_id:
                    self._canvas.coords(image_id, x + self.THUMBNAIL_SIZE // 2, y + self.THUMBNAIL_SIZE // 2)

                border_id = canvas_item.get("border_id", "")
                if border_id:
                    x1, y1, x2, y2 = self._get_item_bounds(item)
                    self._canvas.coords(border_id, x1 - 4, y1 - 4, x2 + 4, y2 + 4)

                placeholder_id = canvas_item.get("placeholder_id", "")
                if placeholder_id:
                    try:
                        self._canvas.coords(placeholder_id, x + self.THUMBNAIL_SIZE // 2, y + self.THUMBNAIL_SIZE // 2)
                    except tk.TclError:
                        pass
                self._canvas.coords(canvas_item["image_info_id"],  x + self.THUMBNAIL_SIZE // 2, self._get_text_y(y))
                self._canvas.itemconfig(canvas_item["image_info_id"], width=self.THUMBNAIL_SIZE)
                self._create_action_buttons(item)

            # 缩略图尺寸变了，清除缓存和加载队列以新尺寸重新加载
            self._visible_image_data.clear()
            self._loading_tasks.clear()
            self._load_visible_images()

        item_height = self._get_item_height()
        rows = math.ceil(len(self._results) / self._cols) if self._cols > 0 else 0
        total_height = rows * item_height + self.MARGIN * 2 if rows > 0 else 0
        if total_height > canvas_height:
            self._canvas.configure(scrollregion=(0, 0, canvas_width, total_height))
        else:
            self._canvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))
            self._canvas.yview_moveto(0)
    
    def _get_item_position(self, item: str) -> tuple[int, int]:
        if self._cols == 0:
            return (self.MARGIN, self.MARGIN)
        
        index = self._get_item_index(item)
        row = index // self._cols
        col = index % self._cols
        
        item_width = self.THUMBNAIL_SIZE + self._h_gap
        item_height = self._get_item_height()
        
        x = col * item_width + self.MARGIN + self.MARGIN // 2
        y = row * item_height + self.MARGIN + self.MARGIN // 2
        
        return (x, y)        
    
    def _load_visible_images(self) -> None:
        if self._is_destroy or not self._results or self._cols == 0:
            return
        
        canvas_y1 = self._canvas.canvasy(0)
        canvas_y2 = canvas_y1 + self._canvas.winfo_height()
        item_height = self._get_item_height()
        
        start_row = max(0, canvas_y1 // item_height - self.PRELOAD_ROWS)
        end_row = min(math.ceil(len(self._results) / self._cols), canvas_y2 // item_height + self.PRELOAD_ROWS)
        start_index = int(start_row * self._cols)
        end_index = int(min(end_row * self._cols - 1, len(self._results) - 1))
        new_visible_items = set()
        for index, item in enumerate(self._results):
            if index < start_index or index > end_index:
                continue
            new_visible_items.add(item)
            if (item not in self._visible_image_data and item not in self._loading_tasks):
                self._loading_tasks.add(item)
                image_path = self._results[item][0]
                self._image_loader.add_task(item, image_path, self.THUMBNAIL_SIZE)
        self._visible_items = new_visible_items

# 对外接口--------------------------------------------------------------------------------------------

    def set_search_text(self, text: str) -> None:
        self._search_text = text

    def sort_results(self, sort_key: str) -> None:
        if not self._results:
            return

        sort_map = {
            "相似度": (2, True),
            "文件名": (-1, False),
            "大小": (0, True),
            "修改时间": (1, True),
        }
        if sort_key not in sort_map:
            return

        col, reverse = sort_map[sort_key]
        if col == -1:
            sorted_items = sorted(
                self._results.items(),
                key=lambda x: Path(x[1][0]).stem.lower(),
                reverse=reverse
            )
        elif col == 0:
            sorted_items = sorted(
                self._results.items(),
                key=lambda x: x[1][col].rstrip("MB"),
                reverse=reverse
            )
        elif col == 2:
            sorted_items = sorted(
                self._results.items(),
                key=lambda x: x[1][col].rstrip("%"),
                reverse=reverse
            )
        else:
            sorted_items = sorted(
                self._results.items(),
                key=lambda x: x[1][col],
                reverse=reverse
            )

        self._results = OrderedDict(sorted_items)
        # 保存旧选中
        old_selection = set(self._selected_items)
        # 清理并重建
        self._cancel_timer()
        self._visible_image_data.clear()
        self._canvas.delete(tk.ALL)
        self._canvas_items.clear()
        self._visible_items.clear()
        self._selected_items.clear()
        self._button_areas.clear()
        self._hovered_button = None
        self._update_layout()
        # 重建占位并恢复选中
        for item in self._results:
            self._create_placeholder(item)
        for item in old_selection:
            if item in self._results:
                self._selected_items.add(item)
                self._set_item_selected(item, True)
        self.parent.after(100, self._load_visible_images)
        self._canvas.event_generate("<<ItemviewSelect>>")
        # 重新启动_check_results轮询
        self._check_results()

    def append_result(self, image_path: str, *extra_info: str | int) -> str:
        item = self._generate_unique_path_item(image_path)
        self._results[item] = (image_path, *extra_info)
        self._update_layout()
        self._create_placeholder(item)
        self.parent.after(100, self._load_visible_images)
        return item

    def clear_results(self) -> None:
        self._cancel_timer()
        self._loading_tasks.clear()
        self._visible_image_data.clear()
        self._results.clear()
        self._canvas_items.clear()
        self._visible_items.clear()
        self._selected_items.clear()
        self._button_areas.clear()
        self._hovered_button = None
        self._canvas.delete(tk.ALL)        
        self._update_layout()
        # 重新启动_check_results轮询，因为_cancel_timer会中断该循环
        self._check_results()

    def selection(self) -> tuple[str, ...]:
        return tuple(self._selected_items)

    def selection_set(self, *items: str) -> None:
        if not items:
            return
        if items[0] == tk.ALL:
            all_need_to_selected_items = set(self._results.keys())
        else:
            all_need_to_selected_items = set(items)
        new_need_to_selected_items = all_need_to_selected_items - self._selected_items
        need_to_deselected_items = self._selected_items - all_need_to_selected_items

        for item in new_need_to_selected_items:
            self._set_item_selected(item, True)

        for item in need_to_deselected_items:
            self._set_item_selected(item, False)

        self._selected_items = all_need_to_selected_items
        self._canvas.event_generate("<<ItemviewSelect>>")

    def identify_item(self, event: tk.Event) -> str:
        x = self._canvas.canvasx(event.x)
        y = self._canvas.canvasy(event.y)
        clicked_item = ""
        for item in self._results:
            item_x1, item_y1, item_x2, item_y2 = self._get_item_bounds(item)
            if item_x1 <= x <= item_x2 and item_y1 <= y <= item_y2:
                clicked_item = item
                break
        return clicked_item

    def bind(self, sequence: str, func: Callable) -> None:
        self._canvas.bind(sequence, func)

    def destroy(self) -> None:
        self._is_destroy = True
        self._cancel_timer()
        self._image_loader.stop()
        self._scrollbar.destroy()
        self._canvas.destroy()




