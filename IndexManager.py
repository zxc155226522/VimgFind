from pathlib import Path
from typing import Literal, Callable
import json
import logging
import re

import numpy as np
try:
    import hnswlib
except ModuleNotFoundError:
    hnswlib = None


from utils import FileOperation



class VectorIndexManager:
    def __init__(
            self, 
            index_path: str, 
            index_capacity: int,
            space: Literal["l2", "cosine"],
            dim: int
        ) -> None:
        self.__index_path: str = index_path
        self.__index_capacity: int = index_capacity
        self.__space: Literal["l2", "cosine"] = space
        self.__dim: int = dim
        self.match: Callable = lambda: None
        self.__init_index()
        self.__init_match_function()

    def __init_index(self) -> None:
        self.__use_hnsw = hnswlib is not None
        if self.__use_hnsw:
            self.__hnsw_index = hnswlib.Index(space=self.__space, dim=self.__dim)
            if Path(self.__index_path).exists():
                self.__hnsw_index.load_index(self.__index_path, max_elements=self.__index_capacity)
            else:
                self.__hnsw_index.init_index(
                    max_elements=self.__index_capacity, 
                    ef_construction=200, 
                    M=32,
                    random_seed=42
                )
            return

        self.__vectors: dict[int, np.ndarray] = {}
        if not Path(self.__index_path).exists():
            return
        try:
            with open(self.__index_path, "rb") as f:
                data = np.load(f)
                ids = data["ids"]
                vectors = data["vectors"]
                self.__vectors = {int(idx): vector for idx, vector in zip(ids, vectors)}
        except Exception as e:
            logging.error(f"加载备用向量索引失败，已重置索引: {e}")
            self.__vectors = {}

    def __init_match_function(self) -> None:
        if self.__space == "cosine":
            self.match = self.match_with_cosine
        elif self.__space == "l2":
            self.match = self.match_with_l2
        else:
            self.match = lambda: None

    def reset_index(self) -> None:
        FileOperation.delete_file(self.__index_path)
        self.__init_index()

    def save_index(self) -> None:
        if self.__use_hnsw:
            self.__hnsw_index.save_index(self.__index_path)
            return
        ids = np.array(list(self.__vectors.keys()), dtype=np.int64)
        vectors = np.array(list(self.__vectors.values()), dtype=np.float32)
        with open(self.__index_path, "wb") as f:
            np.savez(f, ids=ids, vectors=vectors)

    def add_vector(self, fv: np.ndarray, idx: int) -> None:
        if self.__use_hnsw:
            self.__hnsw_index.add_items(fv, idx)
            return
        self.__vectors[idx] = np.asarray(fv, dtype=np.float32)

    def delete_vector(self, idx: int) -> None:
        try:
            if self.__use_hnsw:
                self.__hnsw_index.mark_deleted(idx)
            else:
                self.__vectors.pop(idx, None)
        except Exception as e:
            logging.error(f"删除向量时出错: {e}")

    def match_with_cosine(self, fv, nc=5):
        if self.__use_hnsw:
            self.__hnsw_index.set_ef(max(100, nc * 2))
            labels, distances = self.__hnsw_index.knn_query(fv, k=nc)
            cos_similarities = 1.0 - distances[0]
            logits_per_image = 100 * cos_similarities
            return logits_per_image, labels[0]
        return self.__match_fallback(fv, nc, "cosine")
    
    def match_with_l2(self, fv, nc=5):
        if self.__use_hnsw:
            self.__hnsw_index.set_ef(max(100, nc * 2))
            query = self.__hnsw_index.knn_query(fv, k=nc)
            similarity = (1 - np.tanh(query[1][0] / 3000)) * 100
            return similarity, query[0][0]
        return self.__match_fallback(fv, nc, "l2")

    def __match_fallback(self, fv, nc: int, space: Literal["l2", "cosine"]):
        if not self.__vectors:
            return np.array([]), np.array([], dtype=np.int64)
        ids = np.array(list(self.__vectors.keys()), dtype=np.int64)
        vectors = np.array(list(self.__vectors.values()), dtype=np.float32)
        query = np.asarray(fv, dtype=np.float32).reshape(-1)
        if space == "cosine":
            similarities = vectors @ query
            order = np.argsort(-similarities)[:nc]
            return 100 * similarities[order], ids[order]
        distances = np.sum((vectors - query) ** 2, axis=1)
        order = np.argsort(distances)[:nc]
        similarity = (1 - np.tanh(distances[order] / 3000)) * 100
        return similarity, ids[order]



class NameIndexManager(object):
    NOTEXISTS = 'NOTEXISTS'
    SKIPPED_META_KEY = "skipped"
    def __init__(self, name_index_path: Path, max_match_count: int) -> None:
        self.__name_index_path = name_index_path
        self.__max_match_count = max_match_count
        self.__inverted_index: dict[str, set[int]] = {}
        self.__existing_paths: set[str] = set()
        self.__init_index()

    @property
    def name_index(self) -> list[list]:
        return self.__name_index
    
    @property
    def existing_paths(self) -> set[str]:
        return self.__existing_paths
    
    @property
    def results_count(self) -> int:
        return min(self.__max_match_count, self.__valid_index_count)
    
    @property
    def valid_index_count(self) -> int:
        return self.__valid_index_count
    
    def update_max_match_count(self, max_match_count: int) -> None:
        self.__max_match_count = max_match_count

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        parts = re.split(r'[\s\-_\.\(\)\[\]\{\}]+', text.lower())
        tokens: set[str] = set()
        for part in parts:
            if not part:
                continue
            tokens.add(part)
            for ch in part:
                if '\u4e00' <= ch <= '\u9fff':
                    tokens.add(ch)
        return tokens

    @staticmethod
    def is_skipped_metainfo(metainfo) -> bool:
        return isinstance(metainfo, dict) and metainfo.get(NameIndexManager.SKIPPED_META_KEY) is True

    @staticmethod
    def get_metainfo_size(metainfo) -> int:
        if NameIndexManager.is_skipped_metainfo(metainfo):
            return metainfo.get("size", 0)
        return metainfo

    def __is_valid_item(self, index_file: str, metainfo) -> bool:
        return index_file != NameIndexManager.NOTEXISTS and not self.is_skipped_metainfo(metainfo)
   
    def __init_index(self) -> None:
        try:
            with open(self.__name_index_path, "r", encoding="utf-8") as f:
                self.__name_index = json.load(f)
        except json.JSONDecodeError:
            self.__name_index = []
        except FileNotFoundError:
            Path.mkdir(self.__name_index_path.parent, exist_ok=True)
            self.__name_index = []
        finally:
            self.__valid_index_count = sum(
                self.__is_valid_item(index_file, metainfo)
                for index_file, metainfo in self.__name_index
            )
        self.__inverted_index.clear()
        self.__existing_paths.clear()
        for idx, (index_file, _) in enumerate(self.__name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                continue
            self.__existing_paths.add(index_file)
            stem = Path(index_file).stem
            for token in self._tokenize(stem):
                self.__inverted_index.setdefault(token, set()).add(idx)
    
    def add_name(self, name: Path | str, idx: int) -> None:
        while idx > len(self.__name_index) - 1:
            self.__name_index.append([NameIndexManager.NOTEXISTS, 0])
        was_valid = self.__is_valid_item(*self.__name_index[idx])
        # 从旧名称的倒排索引和 existing_paths 移除
        old_path = self.__name_index[idx][0]
        if old_path != NameIndexManager.NOTEXISTS:
            self.__existing_paths.discard(old_path)
            for token in self._tokenize(Path(old_path).stem):
                if token in self.__inverted_index:
                    self.__inverted_index[token].discard(idx)
        self.__name_index[idx] = [str(name), FileOperation.get_metainfo(name)]
        self.__existing_paths.add(str(name))
        # 加入新名称的倒排索引
        for token in self._tokenize(Path(name).stem):
            self.__inverted_index.setdefault(token, set()).add(idx)
        if not was_valid:
            self.__valid_index_count += 1

    def add_skipped_name(self, name: Path | str, idx: int) -> None:
        while idx > len(self.__name_index) - 1:
            self.__name_index.append([NameIndexManager.NOTEXISTS, 0])
        was_valid = self.__is_valid_item(*self.__name_index[idx])
        # 从旧名称的倒排索引和 existing_paths 移除
        old_path = self.__name_index[idx][0]
        if old_path != NameIndexManager.NOTEXISTS:
            self.__existing_paths.discard(old_path)
            for token in self._tokenize(Path(old_path).stem):
                if token in self.__inverted_index:
                    self.__inverted_index[token].discard(idx)
        self.__name_index[idx] = [
            str(name),
            {"size": FileOperation.get_metainfo(name), self.SKIPPED_META_KEY: True}
        ]
        if was_valid:
            self.__valid_index_count -= 1
    
    def delete_name(self, idx: int) -> None:
        try:
            was_valid = self.__is_valid_item(*self.__name_index[idx])
            old_path = self.__name_index[idx][0]
            if old_path != NameIndexManager.NOTEXISTS:
                self.__existing_paths.discard(old_path)
                for token in self._tokenize(Path(old_path).stem):
                    if token in self.__inverted_index:
                        self.__inverted_index[token].discard(idx)
            self.__name_index[idx][0] = NameIndexManager.NOTEXISTS
            if was_valid:
                self.__valid_index_count -= 1
        except IndexError:
            pass

    def search_by_name(self, query: str, max_results: int) -> list[tuple[int, str]]:
        query_lower = query.lower()
        query_tokens = self._tokenize(query_lower)
        if not query_tokens:
            return []
        # 用第一个 token 获取候选集，再用后续 token 取交集
        it = iter(query_tokens)
        candidates = set(self.__inverted_index.get(next(it), set()))
        for token in it:
            candidates &= self.__inverted_index.get(token, set())
            if not candidates:
                return []
        if not candidates:
            return []
        results = []
        for idx in candidates:
            path = self.__name_index[idx][0]
            if path == NameIndexManager.NOTEXISTS:
                continue
            name = Path(path).stem.lower()
            if query_lower in name:
                results.append((idx, path))
                if len(results) >= max_results:
                    break
        return results

    def reset_index(self) -> None:
        FileOperation.delete_file(self.__name_index_path)
        self.__init_index()

    def save_index(self) -> None:
        with open(self.__name_index_path, 'w', encoding='utf-8') as f:
            json.dump(self.__name_index, f, ensure_ascii=False, indent=4)


