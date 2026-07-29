import io
import sys

# windowed 模式（console=False）下 PyInstaller 会让 stdout/stderr 为 None，
# 而 encoder.py / search_tools.py 等处有 print 进度输出，此时调用会抛异常。
# 重定向到丢弃型 StringIO：windowed 下安全丢弃，脚本/调试模式下保持正常输出。
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

from control import CoreControl


if __name__ == "__main__":
    win = CoreControl()
    win.mainloop()
