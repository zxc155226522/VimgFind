from pathlib import Path
import logging


from tokenizer import FullTokenizer
from PIL import Image
import numpy as np
import onnxruntime as ort


_GPU_PRIORITY = [
    'DmlExecutionProvider',       # DirectML - 支持所有品牌GPU (NVIDIA/AMD/Intel)
    'CUDAExecutionProvider',      # CUDA - 仅NVIDIA GPU
    'TensorrtExecutionProvider',  # TensorRT - 仅NVIDIA GPU
]

_GPU_PROVIDER_LABELS = {
    'DmlExecutionProvider': 'DirectML (GPU)',
    'CUDAExecutionProvider': 'CUDA (NVIDIA GPU)',
    'TensorrtExecutionProvider': 'TensorRT (NVIDIA GPU)',
    'OpenVINOExecutionProvider': 'OpenVINO (Intel)',
    'CoreMLExecutionProvider': 'CoreML (Apple)',
}

class MultiModalEncoder:
    def __init__(
            self, 
            vocab_path: Path, 
            image_encoder_path: Path, 
            text_encoder_path: Path, 
            mean: np.ndarray,
            std: np.ndarray,
            normalization: bool,
            image_size: int,
            context_length: int
        ) -> None:

        self.__image_size = image_size
        self.__mean = mean
        self.__std = std
        self.__normalization = normalization
        self.__context_length = context_length
        self.__tokenizer = FullTokenizer(vocab_path) if vocab_path.exists() else None
        self.image_session = self._init_onnx_session(image_encoder_path, "图像编码器")
        self.text_session = self._init_onnx_session(text_encoder_path, "文本编码器")
        self.device_info = self._detect_device_info()

    def _detect_device_info(self) -> str:
        """从实际加载的 session 读取正在使用的推理设备"""
        session = self.image_session or self.text_session
        if session is None:
            return "未知"
        actual_providers = session.get_providers()
        for prov in _GPU_PRIORITY:
            if prov in actual_providers:
                return _GPU_PROVIDER_LABELS.get(prov, prov)
        return "CPU"

    def tokenize(self, texts) -> np.ndarray:
        if self.__tokenizer is None:
            return np.ndarray([])
        if isinstance(texts, str):
            texts = [texts]

        all_tokens = []
        for text in texts:
            all_tokens.append(
                [self.__tokenizer.vocab['[CLS]']] +
                self.__tokenizer.convert_tokens_to_ids(
                    self.__tokenizer.tokenize(text)
                )[:self.__context_length - 2] + 
                [self.__tokenizer.vocab['[SEP]']]
            )

        result = np.zeros((len(all_tokens), self.__context_length), dtype=np.int64)
        for i, tokens in enumerate(all_tokens):
            assert len(tokens) <= self.__context_length
            result[i, :len(tokens)] = tokens
        return result

    def _init_onnx_session(self, model_path, name: str = "") -> ort.InferenceSession | None:
        """逐个尝试 GPU provider，验证实际加载成功，失败则跳过。全部失败后回退 CPU。"""
        available = ort.get_available_providers()

        # 逐个 GPU provider 尝试，验证实际可用（get_available_providers 可能误报）
        for prov in _GPU_PRIORITY:
            if prov not in available:
                continue
            try:
                session = ort.InferenceSession(
                    str(model_path),
                    providers=[prov, 'CPUExecutionProvider'],
                    provider_options=[{}, {}]
                )
                actual = session.get_providers()
                if prov in actual:
                    label = _GPU_PROVIDER_LABELS.get(prov, prov)
                    if name:
                        print(f"  [{name}] 使用加速设备: {label}")
                    else:
                        print(f"  使用加速设备: {label}")
                    return session
                else:
                    # Provider 声明可用但实际加载失败（如缺少 cuDNN）
                    tag = _GPU_PROVIDER_LABELS.get(prov, prov)
                    if name:
                        print(f"  [{name}] {tag} 加载失败，尝试下一个...")
                    else:
                        print(f"  {tag} 加载失败，尝试下一个...")
            except Exception as e:
                tag = _GPU_PROVIDER_LABELS.get(prov, prov)
                if name:
                    print(f"  [{name}] {tag} 初始化失败: {e}")
                else:
                    print(f"  {tag} 初始化失败: {e}")

        # 全部 GPU 尝试失败，回退 CPU
        try:
            session = ort.InferenceSession(
                str(model_path),
                providers=['CPUExecutionProvider'],
                provider_options=[{'intra_op_num_threads': 1, 'inter_op_num_threads': 1}]
            )
            if name:
                print(f"  [{name}] 使用 CPU 推理")
            else:
                print(f"  使用 CPU 推理")
            return session
        except Exception as e:
            logging.error(f"加载ONNX模型失败 {model_path}: {e}")
            return None

    def _normalization(self, fv: np.ndarray) -> None:
        if self.__normalization:
            norm = np.linalg.norm(fv, axis=-1, keepdims=True)
            fv[fv == 0] = 1.0
            fv /= norm

    def _preprocess_image(self, img: Image.Image) -> np.ndarray | None:
        # img = img.convert("RGB")
        if img.mode in ('P', 'PA', '1', 'L', 'LA'):
            img = img.convert('RGBA')
        
        if img.mode == 'RGBA':
            # 如果有透明通道，创建白色背景
            background = Image.new('RGB', img.size)
            background.paste(img, mask=img.split()[-1])  # 使用alpha通道作为mask
            img = background
        else:
            img = img.convert("RGB")
        img = img.resize((self.__image_size, self.__image_size), Image.Resampling.BICUBIC)
        img_array = np.asarray(img, dtype=np.float32).transpose(2, 0, 1)
        img_array = (img_array / 255.0 - self.__mean) / self.__std
        img_array = np.expand_dims(img_array, axis=0)
        return img_array

    def encode_image(self, image_obj: Image.Image) -> np.ndarray | None:
        if self.image_session is None:
            return None
        
        try:
            processed_image = self._preprocess_image(image_obj)
            if processed_image is None:
                return None
            input_name = self.image_session.get_inputs()[0].name
            result = self.image_session.run([], {input_name: processed_image})
            image_features = result[0][0]
            self._normalization(image_features)
        except Exception as e:
            logging.error(f"编码图像时出现错误，已跳过: {e}")
            return None
        return image_features
    
    def encode_text(self, input_text: str) -> np.ndarray | None:
        if self.text_session is None or self.__tokenizer is None:
            return None
        try:
            text = self.tokenize(input_text)
            text_features_list = []
            for i in range(len(text)):
                one_text = np.expand_dims(text[i], axis=0)
                text_feature = self.text_session.run([], {self.text_session.get_inputs()[0].name: one_text})[0].squeeze()
                text_features_list.append(text_feature)
            text_features = np.stack(text_features_list, axis=0)
            self._normalization(text_features)
            return text_features
        except Exception as e:
            logging.error(f"编码文字时出现错误: {e}")

