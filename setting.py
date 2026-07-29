import json
from pathlib import Path
from typing import Literal
from datetime import datetime
import logging
import ctypes


class Setting(object):
    config_path = Path("./config/setting.json")
    help_path = Path("./config/readme.pdf")
    temp_image_path = Path("./temp")
    error_log = Path("./config/error.log")
    accepted_exts = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif', '.webp'}
    schedule_save_interval = 600000

    def __init__(self) -> None:
        Path.mkdir(Setting.temp_image_path, exist_ok=True)
        Setting._setup_logging()
        self.__config: dict = self.load_settings()

    @classmethod
    def _setup_logging(cls) -> None:
        handler = logging.FileHandler(cls.error_log, encoding='utf-8')
        handler.setLevel(logging.ERROR)
        handler.setFormatter(logging.Formatter('%(asctime)s -  %(message)s'))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        cls._log_handler = handler

    @classmethod
    def _release_logging(cls) -> None:
        handler = getattr(cls, '_log_handler', None)
        if handler is not None:
            root_logger = logging.getLogger()
            root_logger.removeHandler(handler)
            handler.close()
            cls._log_handler = None

    def clean_log(self) -> None:
        self._release_logging()
        try:
            if not Setting.error_log.exists():
                return
            with open(Setting.error_log, "r", encoding="utf-8") as f:
                content = f.readlines()
            with open(Setting.error_log, "w", encoding="utf-8") as f:
                for line in content:
                    try:
                        target_date = datetime.fromisoformat(line.split(" ")[0])
                        current_date = datetime.today()
                        delta_days = (current_date - target_date).days
                        if delta_days < 7:
                            f.write(line)
                    except (ValueError, IndexError):
                        pass
        finally:
            self._setup_logging()

    def get_config(self, config_type: Literal["model", "index", "function"], key: str):
        config_type_key = f"{config_type}_config"
        try:
            return self.__config[config_type_key][key]
        except KeyError:
            return self._default_config()[config_type_key].get(key)

    def modity_config(self, config_type: Literal["model", "index", "function"], key: str, content) -> None:
        self.__config[f"{config_type}_config"][key] = content

    @staticmethod
    def _default_config() -> dict:
        return {
            "model_config": {},
            "index_config": {"max_match_count": 300, "search_dir": []},
            "function_config": {
                "max_work_thread": 4,
                "preview_mode": "medium_ico",
                "auto_update_index": False,
                "ui_style": "superhero",
                "photoshop_path": "",
                "similarity_threshold": 0.0,
                "window_geometry": "",
            },
        }

    def load_settings(self):
        try:
            with open(Setting.config_path, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return self._default_config()
        
    def save_settings(self) -> None:
        with open(Setting.config_path, "w", encoding="utf-8") as f:
            json.dump(self.__config, f, indent=4, ensure_ascii=False)




class WinInfo(object):
    scale_factor = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
    ico_path = "config/favicon.ico"
    title = "Vimgfind"
    width = 1400
    height = 850

    @staticmethod
    def TkS(value: int | float, restore: bool = False) -> int:
        if not restore:
            return int(round(value * WinInfo.scale_factor, 0))
        else:
            return int(round(value / WinInfo.scale_factor, 0))






