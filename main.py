import io
import os
import sys

# PyInstaller 打包后，切换工作目录到 EXE 所在目录，
# 确保 config/ 等相对路径资源可正确解析
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

# windowed 模式（console=False）下 PyInstaller 会让 stdout/stderr 为 None，
# 而 encoder.py / search_tools.py 等处有 print 进度输出，此时调用会抛异常。
# 重定向到丢弃型 StringIO：windowed 下安全丢弃，脚本/调试模式下保持正常输出。
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

# 全局异常钩子：未捕获的异常写入 crash.log，便于定位闪退原因
import traceback

def _crash_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    with open("crash.log", "w", encoding="utf-8") as f:
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)

sys.excepthook = _crash_handler

from control import CoreControl


if __name__ == "__main__":
    win = CoreControl()
    win.mainloop()
