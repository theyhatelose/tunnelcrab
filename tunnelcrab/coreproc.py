import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .paths import singbox_binary_path, xray_binary_path

_ALLOWED_CONFIG_NAMES = {"sing-box.json", "sing-box-bridge.json", "xray.json"}


class RuntimeErrorBase(RuntimeError):
    pass


class UnsupportedPlatformError(RuntimeErrorBase):
    pass


class CoreMissingError(RuntimeErrorBase):
    pass


class PrivilegeError(RuntimeErrorBase):
    pass


_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


_STALE_TUN_MARKERS = (
    "cannot create a file when that file already exists",
    "file already exists",
    "configure tun interface",
)


def is_stale_tunnel_error(text):
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in _STALE_TUN_MARKERS)


def extract_error(log_text):
    lines = [line.strip() for line in log_text.splitlines() if line.strip()]
    if not lines:
        return "Подключение оборвалось без понятной подсказки"

    for line in reversed(lines):
        if "FATAL" in line:
            return line
        if "ERROR" in line:
            return line
        if "error" in line.lower():
            return line

    return lines[-1]


def core_path_for(check):
    return singbox_binary_path() if check == "singbox" else xray_binary_path()


def missing_binaries(plan):
    missing = []
    for step in plan.get("steps", []):
        path = core_path_for(step.get("check"))
        if not path.exists():
            missing.append(str(path))
    return missing


def flush_dns():
    try:
        subprocess.run(
            ["ipconfig", "/flushdns"],
            creationflags=_CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
    except Exception:
        pass


def kill_stray_cores():
    for image in ("sing-box.exe", "xray.exe"):
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", image, "/T"],
                creationflags=_CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
            )
        except Exception:
            pass


class CoreProcessManager:
    def __init__(self):
        self.processes = []
        self.runtime_dir = None
        self._job = None

    def start(self, plan):
        self.stop()
        self._prepare_runtime_dir()
        try:
            for index, step in enumerate(plan.get("steps", [])):
                check = step.get("check")
                if check not in ("singbox", "xray"):
                    raise RuntimeErrorBase("Недопустимый тип ядра в плане подключения")
                config_name = os.path.basename(str(step.get("config_filename") or ""))
                if config_name not in _ALLOWED_CONFIG_NAMES:
                    raise RuntimeErrorBase("Недопустимое имя файла конфигурации")
                config_json = step.get("config_json")
                if not isinstance(config_json, str):
                    raise RuntimeErrorBase("Конфигурация ядра имеет неверный формат")
                core_path = core_path_for(check)
                config_path = self.runtime_dir / config_name
                config_path.write_text(config_json, encoding="utf-8")
                self._check(check, core_path, config_path)
                log_name = f"core-{index}.log"
                self._launch(step.get("name") or check, [str(core_path), "run", "-c", str(config_path)], log_name)
        except Exception:
            self.stop()
            raise

    def _check(self, check, core_path, config_path):
        if check == "singbox":
            args = [str(core_path), "check", "-c", str(config_path)]
        else:
            args = [str(core_path), "run", "-test", "-c", str(config_path)]
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            creationflags=_CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            return
        details = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        raise RuntimeErrorBase(extract_error(details))

    def _launch(self, name, args, log_name):
        log_path = self.runtime_dir / log_name
        log_file = log_path.open("w", encoding="utf-8")
        proc = subprocess.Popen(
            args,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=_CREATE_NO_WINDOW,
        )
        self._assign_to_job(proc)
        self.processes.append({"name": name, "proc": proc, "log_path": log_path, "log_file": log_file})
        return proc

    def is_running(self):
        if not self.processes:
            return False
        return all(entry["proc"].poll() is None for entry in self.processes)

    def poll_error(self):
        if not self.processes:
            return None
        if all(entry["proc"].poll() is None for entry in self.processes):
            return None
        return extract_error(self.read_log())

    def read_log(self):
        chunks = []
        for entry in self.processes:
            log_path = entry["log_path"]
            if not log_path or not log_path.exists():
                continue
            try:
                text = log_path.read_text(encoding="utf-8", errors="ignore").strip()
            except OSError:
                continue
            if text:
                chunks.append(f"[{entry['name']}]\n{text}")
        return "\n".join(chunks)

    def log_tail(self, limit=10):
        lines = [line for line in self.read_log().splitlines() if line.strip()]
        return lines[-limit:]

    def stop(self):
        processes = self.processes
        self.processes = []
        for entry in reversed(processes):
            proc = entry["proc"]
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
            log_file = entry.get("log_file")
            if log_file:
                try:
                    log_file.close()
                except OSError:
                    pass
        if processes:
            flush_dns()
        self._close_job()
        self._cleanup_runtime_dir()

    def _prepare_runtime_dir(self):
        self._cleanup_runtime_dir()
        self.runtime_dir = Path(tempfile.mkdtemp(prefix="tunnelcrab-"))

    def _cleanup_runtime_dir(self):
        if self.runtime_dir:
            shutil.rmtree(self.runtime_dir, ignore_errors=True)
        self.runtime_dir = None

    def _ensure_job(self):
        if self._job is not None:
            return self._job
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                return None

            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_void_p),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_uint64),
                    ("WriteOperationCount", ctypes.c_uint64),
                    ("OtherOperationCount", ctypes.c_uint64),
                    ("ReadTransferCount", ctypes.c_uint64),
                    ("WriteTransferCount", ctypes.c_uint64),
                    ("OtherTransferCount", ctypes.c_uint64),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
            JobObjectExtendedLimitInformation = 9

            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            kernel32.SetInformationJobObject(
                job,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            self._job = job
            return job
        except Exception:
            return None

    def _assign_to_job(self, proc):
        try:
            job = self._ensure_job()
            if not job:
                return
            import ctypes

            handle = int(proc._handle)
            ctypes.windll.kernel32.AssignProcessToJobObject(job, handle)
        except Exception:
            pass

    def _close_job(self):
        if self._job:
            try:
                import ctypes

                ctypes.windll.kernel32.CloseHandle(self._job)
            except Exception:
                pass
            self._job = None
