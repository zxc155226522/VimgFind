# GPU 支持 + exe 打包计划

## 已完成

### 1. ✅ 代码修改（`encoder.py`）
`_init_onnx_session` 已改为自动检测 GPU Provider：
- 优先级：`DmlExecutionProvider` → `CUDAExecutionProvider` → `TensorrtExecutionProvider` → `CPUExecutionProvider`
- 启动时打印使用的是哪个设备
- 已通过实际模型加载测试（DML 加载成功）

### 2. ✅ 环境验证
已安装 `onnxruntime-directml==1.23.0`，实际加载 ONNX 模型测试通过。

## 方案确认：onnxruntime-directml

### 兼容性
| 电脑配置 | 效果 |
|----------|------|
| **你的 GTX 1660 Super** | ✅ GPU 加速（DirectML） |
| **其他 NVIDIA 显卡**（GTX/RTX 全系列） | ✅ GPU 加速（DirectML） |
| **AMD 显卡** | ✅ GPU 加速（DirectML） |
| **Intel 集显**（支持 DirectX 12） | ✅ GPU 加速（DirectML） |
| **没有独立显卡** | ✅ 自动降级 CPU |

### 不需要额外装任何东西
- ❌ 不需要 CUDA Toolkit
- ❌ 不需要 cuDNN
- ✅ 只需要 Windows 10/11 自带 DirectX 12 支持

## 打包后的离线分发

### 打包方式
PyInstaller 自动收集 `DirectML.dll` + `onnxruntime.dll` 等必要 DLL，打包到 `dist/VimgFind/_internal/` 目录下。用户拿到的 exe 直接双击运行，不需要联网安装任何东西。

### 使用方式
在你这台机器上打包一次，把整个 `dist/VimgFind/` 文件夹压缩发给别人，对方解压后双击 `VimgFind.exe` 即可。

### 包大小预估
`onnxruntime-directml` 本身约 25MB（pip 包）+ DirectML.dll（~10MB），打包后整体体积增量约 40-50MB。
