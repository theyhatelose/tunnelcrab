import ctypes
import time

from .platform import is_windows


ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    def __init__(self, name):
        self.name = name
        self._handle = None

    def acquire(self, retries=0, delay=0.25):
        if not is_windows():
            return True

        attempt = 0
        while True:
            handle = ctypes.windll.kernel32.CreateMutexW(None, False, self.name)
            if not handle:
                self._handle = handle
                return True
            if ctypes.GetLastError() != ERROR_ALREADY_EXISTS:
                self._handle = handle
                return True
            ctypes.windll.kernel32.CloseHandle(handle)
            if attempt >= retries:
                return False
            attempt += 1
            time.sleep(delay)

    def release(self):
        if self._handle:
            ctypes.windll.kernel32.ReleaseMutex(self._handle)
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None


def show_already_running_message():
    if not is_windows():
        return

    ctypes.windll.user32.MessageBoxW(
        None,
        "TunnelCrab уже открыт",
        "TunnelCrab",
        0x40,
    )
