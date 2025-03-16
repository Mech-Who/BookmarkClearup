import time
import logging

class LoggerMeta(type):
    def __new__(cls, name, bases, attrs):
        new_class = super().__new__(cls, name, bases, attrs)
        # 添加日志记录功能
        if not hasattr(new_class, "log"):
            new_class.log = logging.getLogger(name)
        return new_class


class TimmingMeta(type, metaclass=LoggerMeta):
    def __new__(cls, name, bases, dct):
        for attr_name, attr_value in dct.items():
            if callable(attr_value):  # 如果是方法，则添加性能监控装饰器
                dct[attr_name] = cls.performance_monitor(attr_value)
        return super().__new__(cls, name, bases, dct)

    @staticmethod
    def performance_monitor(func):
        import time
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            print(f"{func.__name__} took {end_time - start_time:.4f} seconds")
            return result
        return wrapper