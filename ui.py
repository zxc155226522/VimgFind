from ttkbootstrap import Button, Entry, Checkbutton, Radiobutton, Scale, Style, Progressbar
from ttkbootstrap.constants import LINK
from tkinter.ttk import (
    Notebook, Frame, Treeview, Label, LabelFrame, Combobox, Separator
)
from tkinterdnd2 import TkinterDnD
import tkinter as tk
from ctypes import windll


from setting import WinInfo
from widgets import BasicImagePreviewView, PreviewCanvasView



class WinGUI(TkinterDnD.Tk):
    def __init__(self) -> None:
        windll.shcore.SetProcessDpiAwareness(1)
        self._set_dpi_awareness()
        super().__init__()
        self.__win()
        self.switch_tab = self.__set_switch_tab(self)
        self.search_entry = self.__set_search_entry(self.search_tab)
        self.search_btn = self.__set_search_button(self.search_tab)
        self.search_by_browser_btn = self.__set_search_by_browser_button(self.search_tab)
        self.search_by_clipboard_btn = self.__set_search_by_clipboard_button(self.search_tab)
        self.search_setting_bar = self.__set_search_setting_bar(self.search_tab)
        self.preview_container = self.__set_preview_results_frame(self.search_tab)
        self.preview_view = self.__set_preview_view(self.preview_container)
        self.preview_frame1 = self.__set_preview_frame1(self.search_tab)
        self.preview_frame2 = self.__set_preview_frame2(self.search_tab)
        self.preview_canvas1 = PreviewCanvasView(self.preview_frame1)
        self.preview_canvas2 = PreviewCanvasView(self.preview_frame2)
        self.index_dataset_table = self.__set_index_dataset_table(self.setting_tab)
        self.index_tip_label = self.__set_index_tip_label(self.setting_tab)
        self.index_setting_frame = self.__set_index_setting_frame(self.setting_tab)
        self.common_setting_frame = self.__set_common_setting_frame(self.setting_tab)
        self.add_index_button = self.__set_add_index_button(self.index_setting_frame)
        self.update_index_button = self.__set_update_index_button(self.index_setting_frame)
        self.delete_index_button = self.__set_delete_index_button(self.index_setting_frame)
        self.rebuild_index_button = self.__set_rebuild_index_button(self.index_setting_frame)
        self.index_progress_bar = self.__set_index_progress_bar(self.index_setting_frame)
        self.index_progress_label = self.__set_index_progress_label(self.index_setting_frame)
        self.theme_combobox = self.__set_theme_combobox(self.common_setting_frame)
        self.autostart_btn = self.__set_autostart_checkbutton(self.common_setting_frame)
        self.auto_update_btn = self.__set_auto_update_checkbutton(self.common_setting_frame)
        self.update_threads_count_scale = self.__set_update_threads_count_scale(self.common_setting_frame)
        self.open_setting_file_button = self.__set_open_setting_btn(self.common_setting_frame)
        self.open_repertory_button = self.__set_open_open_repertory_btn(self.common_setting_frame)
        self.backup_button = self.__set_backup_button(self.common_setting_frame)
        self.restore_button = self.__set_restore_button(self.common_setting_frame)
        self.device_info_label = self.__set_device_info_label(self.common_setting_frame)
        self.performance_info_label = self.__set_performance_info_label(self.common_setting_frame)

    def _set_dpi_awareness(self) -> None:
        try:
            windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass

    def __win(self) -> None:
        self.title(WinInfo.title)
        screenwidth = self.winfo_screenwidth()
        screenheight = self.winfo_screenheight()
        width = WinInfo.TkS(WinInfo.width)
        hegiht = WinInfo.TkS(WinInfo.height)
        geometry = '%dx%d+%d+%d' % (width, hegiht, (screenwidth - width) // 2, (screenheight - hegiht) // 2)
        self.geometry(geometry)
        self.iconbitmap(WinInfo.ico_path)
        
    def __set_switch_tab(self, parent) -> Notebook:
        frame = Notebook(parent)
        self.search_tab = self.__set_tab_frame(frame)
        frame.add(self.search_tab, text="  检索  ")
        self.setting_tab = self.__set_tab_frame(frame)
        frame.add(self.setting_tab, text="  设置  ")
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        return frame
    
    def __set_tab_frame(self, parent) -> Frame:
        frame = Frame(parent)
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        return frame
    
    def __set_search_entry(self, parent) -> Entry:
        ipt = Entry(parent)
        ipt.place(relx=0.004, rely=0.008, relwidth=0.275, relheight=0.038)
        return ipt

    def __set_search_button(self, parent) -> Button:
        btn = Button(parent, text="搜索", takefocus=False, bootstyle="primary")
        btn.place(relx=0.295, rely=0.007, relwidth=0.08, relheight=0.038)
        return btn

    def __set_search_by_browser_button(self, parent) -> Button:
        btn = Button(parent, text="浏览", takefocus=False,)
        btn.place(relx=0.385, rely=0.007, relwidth=0.1, relheight=0.038)
        return btn
    
    def __set_search_by_clipboard_button(self, parent) -> Button:
        btn = Button(parent, text="剪切板", takefocus=False,)
        btn.place(relx=0.495, rely=0.007, relwidth=0.1, relheight=0.038)
        return btn
    
    def __set_search_setting_bar(self, parent) -> Frame:
        bar = Frame(parent)
        bar.place(relx=0.004, rely=0.05, relwidth=0.6170, relheight=0.04)

        # 预览模式切换按钮
        self.preview_detail_btn = Button(bar, text="详情", takefocus=False, bootstyle="outline-toolbutton")
        self.preview_detail_btn.place(relx=0, rely=0.1, relwidth=0.08, relheight=0.8)

        self.preview_icon_btn = Button(bar, text="图标", takefocus=False, bootstyle="outline-toolbutton")
        self.preview_icon_btn.place(relx=0.09, rely=0.1, relwidth=0.08, relheight=0.8)

        # 路径筛选
        self.path_filter_btn = Button(bar, text="路径: 全部", takefocus=False, bootstyle="outline-toolbutton")
        self.path_filter_btn.place(relx=0.18, rely=0.1, relwidth=0.10, relheight=0.8)

        # 相似度滑块
        self.similarity_label = Label(bar, text="相似度: 0%")
        self.similarity_label.place(relx=0.30, rely=0.2, relwidth=0.12, relheight=0.6)

        self.similarity_scale = Scale(bar, from_=0, to=100, orient=tk.HORIZONTAL, takefocus=False)
        self.similarity_scale.set(0)
        self.similarity_scale.place(relx=0.42, rely=0.15, relwidth=0.17, relheight=0.7)

        # 排序
        self.sort_label = Label(bar, text="排序:")
        self.sort_label.place(relx=0.60, rely=0.2, relwidth=0.04, relheight=0.6)

        self.sort_combo = Combobox(bar, values=("相似度", "文件名", "大小", "修改时间"), state="readonly", width=8)
        self.sort_combo.place(relx=0.64, rely=0.15, relwidth=0.09, relheight=0.7)

        # 结果数量输入
        self.result_count_label = Label(bar, text="输入:")
        self.result_count_label.place(relx=0.74, rely=0.2, relwidth=0.04, relheight=0.6)

        self.result_count_entry = Entry(bar)
        self.result_count_entry.insert(0, "300")
        self.result_count_entry.place(relx=0.78, rely=0.15, relwidth=0.05, relheight=0.7)

        # 搜索模式切换（单选框）
        self._search_mode_var = tk.BooleanVar(value=True)
        self.search_mode_name_rb = Radiobutton(bar, text="文件名", variable=self._search_mode_var,
                                                value=True, takefocus=False)
        self.search_mode_name_rb.place(relx=0.85, rely=0.1, relwidth=0.07, relheight=0.8)
        self.search_mode_semantic_rb = Radiobutton(bar, text="语义", variable=self._search_mode_var,
                                                    value=False, takefocus=False)
        self.search_mode_semantic_rb.place(relx=0.93, rely=0.1, relwidth=0.07, relheight=0.8)

        return bar
    
    def __set_preview_results_frame(self, parent) -> Frame:
        preview_results_frame = Frame(parent)
        preview_results_frame.place(relx=0.004, rely=0.095, relwidth=0.736, relheight=0.897)
        return preview_results_frame
    
    def __set_preview_view(self, parent) -> BasicImagePreviewView:
        basic_preview_view = BasicImagePreviewView(parent)
        return basic_preview_view

    def __set_preview_frame1(self, parent) -> LabelFrame:
        frame = LabelFrame(parent, text="源图片")
        frame.place(relx=0.755, rely=0.05, relwidth=0.22, relheight=0.33)
        return frame
    
    def __set_preview_frame2(self, parent) -> LabelFrame:
        frame = LabelFrame(parent, text="匹配图片")
        frame.place(relx=0.755, rely=0.40, relwidth=0.22, relheight=0.33)
        return frame

    def __set_index_tip_label(self, parent) -> Label:
        label = Label(parent,text="当前索引的图库(~张图片)", anchor=tk.NW, font=("微软雅黑", 14))
        label.place(relx=0.0081, rely=0.04, relwidth=1, relheight=0.0575)
        return label
    
    def __set_index_dataset_table(self, parent) -> Treeview:
        columns = [" ", "图库目录"]
        index_dataset_table = Treeview(parent, show="headings", columns=columns)
        index_dataset_table.heading(0, text=columns[0], anchor=tk.CENTER)
        index_dataset_table.column(0, width=60, anchor=tk.CENTER, stretch=False)
        index_dataset_table.heading(1, text=columns[1], anchor=tk.CENTER)
        index_dataset_table.column(1, anchor=tk.CENTER)
        index_dataset_table.place(relx=0.0081, rely=0.1111, relwidth=0.7, relheight=0.888)
        return index_dataset_table
    
    def __set_index_setting_frame(self, parent) -> LabelFrame:
        frame = LabelFrame(parent, text="索引设置")
        frame.place(relx=0.7181, rely=0.095, relwidth=0.2719, relheight=0.4738)
        for i in range(7):
            frame.grid_rowconfigure(i, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        return frame
    
    def __set_add_index_button(self, parent) -> Button:
        btn = Button(parent, text="添加索引目录", takefocus=False)
        btn.grid(row=0, column=0, padx=5, pady=(10, 5), ipadx=10, ipady=5, sticky=tk.NSEW)
        return btn

    def __set_update_index_button(self, parent) -> Button:
        btn = Button(parent, text="更新索引目录", takefocus=False)
        btn.grid(row=1, column=0, padx=5, pady=5, ipadx=10, ipady=5, sticky=tk.NSEW)
        return btn

    def __set_delete_index_button(self, parent) -> Button:
        btn = Button(parent, text="删除索引目录", takefocus=False)
        btn.grid(row=2, column=0, padx=5, pady=5, ipadx=10, ipady=5, sticky=tk.NSEW)
        return btn

    def __set_rebuild_index_button(self, parent) -> Button:
        btn = Button(parent, text="重建索引目录", takefocus=False)
        btn.grid(row=3, column=0, padx=5, pady=(5, 5), ipadx=10, ipady=5, sticky=tk.NSEW)
        return btn

    def __set_index_progress_bar(self, parent) -> Progressbar:
        bar = Progressbar(parent, mode='determinate', maximum=100, value=0)
        bar.grid(row=4, column=0, padx=10, pady=(2, 0), sticky=tk.EW)
        bar.grid_remove()
        return bar

    def __set_index_progress_label(self, parent) -> Label:
        label = Label(parent, text="", anchor=tk.CENTER, font=("微软雅黑", 9))
        label.grid(row=5, column=0, padx=10, pady=(0, 2), sticky=tk.EW)
        return label

    def __set_common_setting_frame(self, parent) -> LabelFrame:
        frame = LabelFrame(parent, text="通用设置")
        frame.place(relx=0.7181, rely=0.58, relwidth=0.2609+0.011, relheight=0.42)
        for i in range(10):
            frame.grid_rowconfigure(i, weight=1)
        frame.grid_columnconfigure(0, weight=1, uniform='space')
        frame.grid_columnconfigure(1, weight=1, uniform='labels')
        frame.grid_columnconfigure(2, weight=1, uniform='controls')
        frame.grid_columnconfigure(3, weight=1, uniform='space')
        return frame

    def __set_theme_combobox(self, parent) -> Combobox:
        style = Style()
        theme_names = style.theme_names()
        tip = Label(parent, text="界面主题设置")
        tip.grid(row=1, column=1, padx=(5, 10), sticky=tk.E)
        comb = Combobox(parent, values=theme_names, state="readonly", width=15)
        comb.grid(row=1, column=2, padx=(0, 5), sticky=tk.EW)
        return comb

    def __set_autostart_checkbutton(self, parent) -> Checkbutton:
        tip = Label(parent, text="开机启动")
        tip.grid(row=0, column=1, padx=(5, 10), sticky=tk.E)
        checkbtn = Checkbutton(parent, style="square-toggle")
        checkbtn.grid(row=0, column=2, padx=(0, 5), sticky=tk.EW)
        return checkbtn

    def __set_auto_update_checkbutton(self, parent) -> Checkbutton:
        tip = Label(parent, text="自动更新索引")
        tip.grid(row=2, column=1, padx=(5, 10), sticky=tk.E)
        checkbtn = Checkbutton(parent, style="square-toggle")
        checkbtn.grid(row=2, column=2, padx=(0, 5), sticky=tk.EW)
        return checkbtn

    def __set_update_threads_count_scale(self, parent) -> Scale:
        tip = Label(parent, text="更新线程：--")
        tip.grid(row=3, column=1, padx=(5, 10), sticky=tk.E)
        scale = Scale(parent, from_=1, to=32, orient=tk.HORIZONTAL)
        scale.grid(row=3, column=2, padx=(0, 5), sticky=tk.EW)
        scale.config(command=lambda value: tip.config(text=f"更新线程：{int(float(value)):0>2}"))
        return scale
    
    def __set_open_setting_btn(self, parent) -> Button:
        button = Button(parent, text="配置文件", takefocus=True, style=LINK, cursor="hand2")
        button.grid(row=9, column=1, pady=(5, 0), sticky=tk.E)
        return button
    
    def __set_open_open_repertory_btn(self, parent) -> Button:
        button = Button(parent, text="仓库地址", takefocus=True, style=LINK, cursor="hand2")
        button.grid(row=9, column=2, pady=(5, 0), padx=20, sticky=tk.W)
        return button

    def __set_backup_button(self, parent) -> Button:
        button = Button(parent, text="备份数据库", takefocus=False)
        button.grid(row=4, column=1, padx=5, pady=5, ipadx=10, ipady=5, columnspan=2, sticky=tk.EW)
        return button

    def __set_restore_button(self, parent) -> Button:
        button = Button(parent, text="恢复数据库", takefocus=False)
        button.grid(row=5, column=1, padx=5, pady=5, ipadx=10, ipady=5, columnspan=2, sticky=tk.EW)
        return button

    def __set_device_info_label(self, parent) -> Label:
        sep = Separator(parent, orient=tk.HORIZONTAL)
        sep.grid(row=6, column=0, columnspan=4, padx=10, pady=(5, 2), sticky=tk.EW)
        label = Label(parent, text="推理设备：检测中...", anchor=tk.CENTER, font=("微软雅黑", 9))
        label.grid(row=7, column=0, columnspan=4, padx=5, pady=(0, 2), sticky=tk.EW)
        return label

    def __set_performance_info_label(self, parent) -> Label:
        label = Label(parent, text="性能：CPU --% | 内存 --MB (--%)", anchor=tk.CENTER, font=("微软雅黑", 9))
        label.grid(row=8, column=0, columnspan=4, padx=5, pady=(0, 5), sticky=tk.EW)
        return label
    
