from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread, Event
from pathlib import Path
from typing import Iterator
from re import split
import logging
import time


import numpy as np
from PIL import Image

from setting import Setting
from IndexManager import VectorIndexManager, NameIndexManager
from encoder import MultiModalEncoder
from utils import FileOperation, ImageOperation


def _format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "--"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}秒"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}分{seconds:02d}秒"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}小时{minutes:02d}分"


def _format_progress(stage: str, done: int, total: int, start_time: float) -> str:
    elapsed = max(time.time() - start_time, 0.001)
    if total <= 0:
        return f"{stage}：0/0"
    percent = done / total * 100
    speed = done / elapsed if done > 0 else 0
    eta = (total - done) / speed if speed > 0 else None
    return f"{stage}：{done}/{total} ({percent:.1f}%) | {speed:.1f}张/秒 | 剩余 {_format_duration(eta)}"


class SearchTool(object):
    def __init__(self, setting: Setting) -> None:
        self.__search_event = Event()
        self.__search_event.set()
        self.__init_event = Event()
        self.__force_stop_update = False
        Thread(target=self.__async_init, args=(setting, ), daemon=True).start()
        
    def __async_init(self, setting: Setting) -> None:
        self.__vec_idx_mgr = VectorIndexManager(
            setting.get_config("index", "vector_index_path"),
            setting.get_config("index", "index_capacity"),
            setting.get_config("index", "index_space"),
            setting.get_config("index", "index_dim")
        )
        self.__name_idx_mgr = NameIndexManager(
            Path(setting.get_config("index", "name_index_path")),
            setting.get_config("index", "max_match_count")
        )
        self.__similarity_threshold = setting.get_config("function", "similarity_threshold")
        self.__multimodal_encoder = MultiModalEncoder(
            Path(setting.get_config("model", "vocab_path")),
            Path(setting.get_config("model", "image_encoder_path")),
            Path(setting.get_config("model", "text_encoder_path")),
            np.array(setting.get_config("model", "mean"), dtype=np.float32)[:, None, None],
            np.array(setting.get_config("model", "std"), dtype=np.float32)[:, None, None],
            setting.get_config("model", "normalization"),
            setting.get_config("model", "image_size"),
            setting.get_config("model", "context_length")
        )
        self.__init_event.set()

    @property
    def valid_index_count(self) -> int:
        self.__init_event.wait()
        return self.__name_idx_mgr.valid_index_count

    def get_device_info(self) -> str:
        self.__init_event.wait()
        return getattr(self.__multimodal_encoder, 'device_info', '未知')

    def __get_changed_files_index(self) -> list[tuple[int, str]]:
        changed_files_index = []
        for idx, [index_file, old_metainfo] in enumerate(self.__name_idx_mgr.name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                continue
            new_metainfo = FileOperation.get_metainfo(index_file)
            if NameIndexManager.get_metainfo_size(old_metainfo) != new_metainfo:
                changed_files_index.append((idx, index_file))
        return changed_files_index
    
    def __get_new_files_index(self, target_dir: str) -> list[tuple[int, str]]:
        new_files_index = []
        current_files, total_files = FileOperation.get_file_iterator(target_dir)
        existing_files = self.__name_idx_mgr.existing_paths
        new_files = []
        scanned_count = 0
        scan_start_time = time.time()
        last_report_time = 0.0
        print(f"扫描文件：{target_dir}（共 {total_files} 个）")
        for file in current_files:
            scanned_count += 1
            if file not in existing_files:
                new_files.append(file)
            now = time.time()
            if scanned_count % 200 == 0 or now - last_report_time >= 1:
                filename = Path(file).name
                print(f"扫描：{scanned_count}/{total_files} | {filename} | 新增 {len(new_files)}个")
                last_report_time = now
            if self.__force_stop_update:
                break
        print(f"扫描完成：{scanned_count}/{total_files}个 | 新增 {len(new_files)}个 | 耗时 {_format_duration(time.time() - scan_start_time)}")

        if not new_files:
            return []

        for idx, [index_file, _] in enumerate(self.__name_idx_mgr.name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                new_files_index.append((idx, new_files.pop())) 
            if len(new_files) == 0:
                break
        for idx, new_file in enumerate(new_files, len(self.__name_idx_mgr.name_index)):
            new_files_index.append((idx, new_file))

        return new_files_index

    def __index_target_dir(self, target_dir) -> list[tuple[int, str]]:
        changed_files_index = self.__get_changed_files_index()
        new_files_index = self.__get_new_files_index(target_dir)
        return changed_files_index + new_files_index
    
    def update_max_match_count(self, max_match_count: int) -> None:
        self.__name_idx_mgr.update_max_match_count(max_match_count)

    def update_similarity_threshold(self, threshold: float) -> None:
        self.__similarity_threshold = threshold
        
    def update_index(self, image_dir, max_workers: int = 10) -> None:
        def _process_item(item) -> tuple[int, str, np.ndarray | None, bool]:
            self.__search_event.wait()
            idx, fpath = item
            if self.__force_stop_update:
                return idx, fpath, None, False
            try:
                image_obj = ImageOperation.get_image_obj(fpath)
                if image_obj is None:
                    return idx, fpath, None, True
                fv = self.__multimodal_encoder.encode_image(image_obj)
            except Exception as e:
                logging.error(f"处理图片失败，已跳过 {fpath}: {e}")
                return idx, fpath, None, True
            return idx, fpath, fv, fv is None
        self.__init_event.wait()
        need_to_update = self.__index_target_dir(image_dir)
        total = len(need_to_update)
        if total == 0:
            print("更新索引：无需更新")
            return
        update_start_time = time.time()
        last_report_time = 0.0
        completed_count = 0
        print(_format_progress("更新索引", completed_count, total, update_start_time))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_process_item, item) for item in need_to_update]
            for future in as_completed(futures):
                idx, fpath, fv, skipped = future.result()
                if fv is not None:
                    self.__vec_idx_mgr.add_vector(fv, idx)
                    self.__name_idx_mgr.add_name(fpath, idx)
                elif skipped:
                    self.__vec_idx_mgr.delete_vector(idx)
                    self.__name_idx_mgr.add_skipped_name(fpath, idx)
                completed_count += 1
                now = time.time()
                if completed_count == total or now - last_report_time >= 0.2:
                    print(_format_progress("更新索引", completed_count, total, update_start_time))
                    last_report_time = now
    
    def remove_nonexists(self) -> None:
        self.__init_event.wait()
        total = len(self.__name_idx_mgr.name_index)
        if total == 0:
            print("清理失效索引：无需清理")
            return
        clean_start_time = time.time()
        last_report_time = 0.0
        removed_count = 0
        for idx, (index_file, _) in enumerate(self.__name_idx_mgr.name_index):
            done = idx + 1
            if not (Path(index_file).exists() or index_file == NameIndexManager.NOTEXISTS):
                self.__name_idx_mgr.delete_name(idx)
                self.__vec_idx_mgr.delete_vector(idx)
                removed_count += 1
            now = time.time()
            if done == total or now - last_report_time >= 0.2:
                print(f"{_format_progress('清理失效索引', done, total, clean_start_time)} | 移除 {removed_count}个")
                last_report_time = now

    def remove_files_in_directory(self, directory: str) -> None:
        self.__init_event.wait()
        directory_path = Path(directory).resolve()
        for idx, (index_file, _) in enumerate(self.__name_idx_mgr.name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                continue
            file_path = Path(index_file).resolve()
            if not file_path.is_relative_to(directory_path):
                continue
            self.__name_idx_mgr.delete_name(idx)
            self.__vec_idx_mgr.delete_vector(idx)

    def checkout(self, content: Image.Image | str) -> Iterator[tuple[str, float]]:
        self.__init_event.wait()
        results_count = self.__name_idx_mgr.results_count
        if results_count == 0 or (isinstance(content, str) and content == ""):
            return
        self.stop_update_index()
        if isinstance(content, Image.Image):
            fv = self.__multimodal_encoder.encode_image(content)
        else:
            keywords = split(r"[\s|,]", content)
            if len(keywords) > 1:
                combine_sentence = f"一张照片同时包含了{'、'.join(keywords[:-2])}和{keywords[-1]}"
            else:
                combine_sentence = content
            fv = self.__multimodal_encoder.encode_text(combine_sentence)

        if fv is None:
            return

        search_count = min(results_count * 3, self.__name_idx_mgr.valid_index_count)
        sim_list, ids_list = self.__vec_idx_mgr.match(fv, search_count)

        yielded = 0
        for img_id, similarity in zip(ids_list, sim_list):
            if similarity < self.__similarity_threshold * 100:
                continue
            yield (self.__name_idx_mgr.name_index[img_id][0], similarity)
            yielded += 1
            if yielded >= results_count:
                break
        self.continue_update_index()

    def checkout_by_name(self, query: str) -> Iterator[tuple[str, float]]:
        """按文件名搜索（使用倒排索引加速）"""
        self.__init_event.wait()
        if not query:
            return
        results = self.__name_idx_mgr.search_by_name(query, self.__name_idx_mgr.results_count)
        for _, path in results:
            yield (path, 100.0)

    def is_empty_index(self) -> bool:
        return self.__name_idx_mgr.results_count == 0
    
    def reset_index(self) -> None:
        self.__init_event.wait()
        self.__vec_idx_mgr.reset_index()
        self.__name_idx_mgr.reset_index()

    def save_index(self) -> None:
        self.__init_event.wait()
        try:
            self.__vec_idx_mgr.save_index()
            self.__name_idx_mgr.save_index()
        except Exception as e:
            logging.error(f"保存索引时出现错误: {e}")

    def stop_update_index(self) -> None:
        self.__search_event.clear()

    def set_force_end_update(self, state: bool) -> None:
        self.__force_stop_update = state

    def continue_update_index(self) -> None:
        self.__search_event.set()

    def destroy(self) -> None:
        self.__search_event.set()
        self.__init_event.set()

