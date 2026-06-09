import json
import socket
import threading


class IpcError(Exception):
    pass


class IpcServer:
    def __init__(self, token, handler):
        self.token = token
        self.handler = handler
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.port = self.sock.getsockname()[1]
        self._stop = threading.Event()

    def serve_forever(self):
        self.sock.settimeout(1.0)
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle_conn, args=(conn,), daemon=True).start()

    def _handle_conn(self, conn):
        try:
            handle = conn.makefile("rwb")
            line = handle.readline()
            if not line:
                return
            try:
                message = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._send(handle, {"ok": False, "error": "bad_request"})
                return
            if message.get("token") != self.token:
                self._send(handle, {"ok": False, "error": "unauthorized"})
                return
            response = self.handler(message)
            self._send(handle, response if isinstance(response, dict) else {"ok": True})
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    @staticmethod
    def _send(handle, obj):
        try:
            handle.write((json.dumps(obj) + "\n").encode("utf-8"))
            handle.flush()
        except OSError:
            pass

    def stop(self):
        self._stop.set()
        try:
            self.sock.close()
        except OSError:
            pass


def request(port, token, payload, timeout=10):
    body = dict(payload)
    body["token"] = token
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall((json.dumps(body) + "\n").encode("utf-8"))
            handle = sock.makefile("rb")
            line = handle.readline()
    except OSError as exc:
        raise IpcError(str(exc))
    if not line:
        raise IpcError("no_response")
    try:
        return json.loads(line.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise IpcError(str(exc))
