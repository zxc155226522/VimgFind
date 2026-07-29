# 修改计划

## 问题分析

### 1. GPU/CPU 使用状态显示
- `encoder.py` 的 `_init_onnx_session()` 中已通过 `ort.get_available_providers()` 检测可用设备
- 但当前没有在 UI 上显示当前使用的推理设备（GPU/CPU）
- 需要在界面某处显示设备信息

### 2. 搜索后切换图标/详情报错
`SearchControl.set_preview_mode()`（control.py:390-408）在切换视图时存在以下问题：
- **`DetailListView` 的 `_results` key 混淆**：`append_result` 中 `_results[iid] = (image_path, *extra_info)` 存储了 (path, size, mtime, sim)。当切换到 `ThumbnailGridView` 时，`get_show_results()` 返回 `[(path, size, mtime, sim)]`，然后 `img_path, *extra_info = result` → `extra_info = (size, mtime, sim)`，重新存入新视图。**但 `DetailListView` 在 Treeview 中实际显示的是 `(basename, size, mtime, sim)`，而 `_results` 存的是 `(path, size, mtime, sim)`**，两者不一致。切换时重建的数据是正确路径格式，但 DetailListView 自身显示时 basename 是通过 `os.path.basename(image_path)` 在每项插入时动态生成的，这不是 bug，只是 design choice。
- **`DetailListView._load_thumbnail_async` 的后台线程**：当视图被 `destroy()` 后，后台加载线程仍在运行，之后调用 `_set_thumbnail` 会操作已销毁的 `__treeview`。`exists(iid)` 检查在 Treeview 销毁后可能抛出异常。
- **`ThumbnailGridView.sort_results` 排序后触发 `<<ItemviewSelect>>`**（control.py:1015），导致 100ms 后执行 `_do_preview_item`，但如果此时视图已切换回 DetailListView（快速连续点击），可能引发 KeyError 或其他问题。

### 3. 线程数修改
- UI 中已有 `update_threads_count_scale`（from_=4, to=20）
- `destroy()` 时已保存到 `setting.json` 的 `max_work_thread`
- `sync_index()` 中已读取并使用该值
- **但初始文本格式不一致**：初始化 `tip = Label(text=f"更新线程：04")` 使用全角冒号，而 command lambda 使用半角冒号
- **用户想要的功能可能已经实现了**，但可能需要：
  - 让线程数量的范围更灵活（如 1-32）
  - 或者初始显示没有正确反映保存的值

## 修改方案

### 修改 1：GPU/CPU 显示
- 在 `ui.py` 的 `common_setting_frame` 底部添加一个 LabelFrame 用于显示设备信息
- 在 `encoder.py` 的 `MultiModalEncoder` 中添加 `device_info` 属性，记录使用的设备
- 在 `control.py` 的 `__env_init` 中读取设备信息并显示

### 修改 2：修复切换视图报错
- **`DetailListView.destroy()`**：添加 `_is_destroy` 标志，防止后台线程操作已销毁的控件
- **`DetailListView._load_thumbnail_async` / `_set_thumbnail`**：在操作前检查 `_is_destroy`
- **`ThumbnailGridView` 的类似问题**：已有 `_is_destroy` 保护，但需确认 `_check_results` 中的 `_create_canvas_item` 也是安全的
- **`set_preview_mode` 中避免重复触发事件**：在重建过程中临时禁用事件触发

### 修改 3：线程数范围优化
- 扩大 Scale 范围（from_=1, to=32）
- 修复初始文本格式
- 确保保存/读取正确

## 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `ui.py` | 添加设备信息显示区域 |
| `encoder.py` | 添加 `device_info` 属性和 `get_device_info` 方法 |
| `control.py` | 初始化时显示设备信息；修复切换视图的潜在问题；线程初始化值正确显示 |
| `widgets.py` | `DetailListView` 添加 `_is_destroy` 保护 |
| `setting.py` | 默认值改为 `max_work_thread: 4`（不变） |
