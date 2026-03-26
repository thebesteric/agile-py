from io import StringIO


class StringBuilder(StringIO):

    def __init__(self, initial_value=None):
        super().__init__(initial_value)
        if initial_value:
            self.seek(len(initial_value))

    def append(self, text):
        """追加字符串，支持链式调用"""
        self.write(text)
        return self  # 支持链式调用

    def to_string(self):
        """获取最终字符串"""
        return self.getvalue()

    def clear(self):
        self.truncate(0)
        self.seek(0)
        return self

    def length(self):
        """获取当前长度"""
        return len(self.to_string())
