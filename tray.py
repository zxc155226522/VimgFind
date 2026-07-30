import threading
import logging

import pystray
from PIL import Image


class TrayManager:
    """系统托盘图标管理器"""

    def __init__(self, icon_path: str, title: str, on_show, on_quit) -> None:
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None
        self._on_show = on_show
        self._on_quit = on_quit
        self._title = title
        try:
            self._image = Image.open(icon_path)
        except Exception:
            self._image = Image.new('RGB', (64, 64), 'white')

    def start(self) -> None:
        if self._icon is not None:
            return
        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", self._on_show, default=True),
            pystray.MenuItem("退出", self._on_quit),
        )
        self._icon = pystray.Icon(self._title, self._image, self._title, menu)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception as e:
                logging.error(f"停止托盘图标时出错: {e}")
            finally:
                self._icon = None
                self._thread = None
