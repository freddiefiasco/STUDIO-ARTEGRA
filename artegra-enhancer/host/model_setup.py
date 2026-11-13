"""Publisher-only model acquisition. No Qt, inference, credentials or model redistribution.

Final files appear only after exact size and SHA-256 verification. Interrupted transfers
remain in a content-addressed .part file and can be resumed after another explicit action.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import errno
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import socket
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid


CHUNK_SIZE = 1024 * 1024


class SetupError(Exception):
    def __init__(self, message, code="setup"):
        super().__init__(message)
        self.code = code


def _check_cancel(cancel):
    if cancel.is_set():
        raise SetupError("Model setup paused. Download again to resume the saved transfer.", "cancelled")


def _safe_url(url, allow_http_loopback=False):
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").lower()
    if parsed.username or parsed.password or parsed.fragment:
        return False
    if allow_http_loopback and parsed.scheme == "http" and host in {"127.0.0.1", "::1"}:
        return True
    return parsed.scheme == "https" and (host == "huggingface.co" or host.endswith(".huggingface.co")
                                         or host.endswith(".hf.co") or host == "hf.co")


class _PublisherRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allow_http_loopback):
        self.allow_http_loopback = allow_http_loopback

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _safe_url(newurl, self.allow_http_loopback):
            raise SetupError("The publisher redirected to an unexpected download location.", "redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _CancellationWatch:
    """Interrupt socket I/O even when a peer keeps the idle timeout alive by dribbling data."""
    def __init__(self, cancel):
        self.cancel = cancel
        self.done = threading.Event()
        self.sockets = []
        self.lock = threading.Lock()

    def add(self, connection):
        with self.lock:
            self.sockets.append(connection)
        if self.cancel.is_set():
            self.interrupt()

    def interrupt(self):
        with self.lock:
            connections = tuple(self.sockets)
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # Already closed by HTTPResponse or a previous redirect.

    def __enter__(self):
        def watch():
            while not self.done.wait(0.02):
                if self.cancel.is_set():
                    self.interrupt()
                    return
        self.thread = threading.Thread(target=watch, name="model-download-cancel", daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.done.set()
        self.thread.join()


class _WatchedConnection:
    def __init__(self, *args, watch, **kwargs):
        self.watch = watch
        super().__init__(*args, **kwargs)

    def connect(self):
        super().connect()
        self.watch.add(self.sock)


class _HTTPConnection(_WatchedConnection, http.client.HTTPConnection):
    pass


class _HTTPSConnection(_WatchedConnection, http.client.HTTPSConnection):
    pass


@contextmanager
def _open_response(request, cancel, allow_http_loopback):
    with _CancellationWatch(cancel) as watch:
        class HTTP(urllib.request.HTTPHandler):
            def http_open(self, req):
                return self.do_open(lambda host, **kw: _HTTPConnection(host, watch=watch, **kw), req)

        class HTTPS(urllib.request.HTTPSHandler):
            def https_open(self, req):
                return self.do_open(lambda host, **kw: _HTTPSConnection(host, watch=watch, **kw),
                                    req, context=self._context)

        opener = urllib.request.build_opener(_PublisherRedirect(allow_http_loopback), HTTP(), HTTPS())
        try:
            with opener.open(request, timeout=10) as response:
                _check_cancel(cancel)
                yield response
        except Exception:
            _check_cancel(cancel)
            raise


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _file_lock(path):
    """OS lock releases on process exit; no stale PID/lock deletion is needed."""
    if path.is_symlink():
        raise SetupError("The download lock is a link. Choose a different model folder.", "path")
    stream = path.open("a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt
            stream.seek(0, 2)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise SetupError("Another model setup is using this folder. Wait for it to finish.", "busy") from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise SetupError("Another model setup is using this folder. Wait for it to finish.", "busy") from exc
        locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()


class ModelSetup:
    def __init__(self, manifest_path, acceptance_path, *, allow_http_loopback=False):
        self.acceptance_path = Path(acceptance_path)
        self.allow_http_loopback = allow_http_loopback
        self._acceptance_lock = threading.Lock()
        try:
            data = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
            if data.get("schema_version") != 1 or not isinstance(data.get("models"), list):
                raise ValueError()
            self.models = {}
            for value in data["models"]:
                model = dict(value)
                identity = model["id"]
                if identity in self.models or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", identity):
                    raise ValueError()
                for key in ("folder", "filename"):
                    name = model[key]
                    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in {".", ".."}:
                        raise ValueError()
                if not re.fullmatch(r"[0-9a-f]{64}", model["sha256"]):
                    raise ValueError()
                if type(model["size_bytes"]) is not int or model["size_bytes"] <= 0:
                    raise ValueError()
                if not _safe_url(model["download_url"], allow_http_loopback):
                    raise ValueError()
                if not model.get("model_card_url") or not model.get("license_url"):
                    raise ValueError()
                self.models[identity] = model
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise SetupError("The model catalogue is missing or invalid. Reinstall the application.", "manifest") from exc

    def _model(self, identity):
        try:
            return self.models[identity]
        except KeyError as exc:
            raise SetupError("This model is not in the application catalogue.", "manifest") from exc

    def _fingerprint(self, model):
        fields = {key: model.get(key) for key in ("id", "sha256", "revision", "license", "license_url",
                                                    "model_card_url", "acceptance_notice", "license_snapshot_sha256")}
        return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()

    def _read_acceptance(self):
        try:
            value = json.loads(self.acceptance_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def accepted(self, identity):
        model = self._model(identity)
        with self._acceptance_lock:
            record = self._read_acceptance().get(identity, {})
        return isinstance(record, dict) and record.get("fingerprint") == self._fingerprint(model)

    def accept(self, identity, accepted):
        model = self._model(identity)
        with self._acceptance_lock:
            records = self._read_acceptance()
            if accepted:
                records[identity] = {"fingerprint": self._fingerprint(model),
                                     "accepted_at": datetime.now(timezone.utc).isoformat(),
                                     "model_card_url": model["model_card_url"], "license_url": model["license_url"]}
            else:
                records.pop(identity, None)
            try:
                _write_json(self.acceptance_path, records)
            except OSError as exc:
                raise SetupError("Your licence choice could not be saved. Check the app's settings folder.", "disk") from exc

    def _paths(self, model, directory, *, create):
        directory = Path(directory).expanduser().resolve()
        if create:
            directory.mkdir(parents=True, exist_ok=True)
        folder = directory / model["folder"]
        path = folder / model["filename"]
        part = path.with_name(path.name + "." + model["sha256"][:16] + ".part")
        lock = directory / ".artegra-model-download.lock"
        for candidate in (folder, path, part, lock):
            if candidate.is_symlink() or not candidate.resolve().is_relative_to(directory):
                raise SetupError("A model path points outside the selected folder. Choose a different folder.", "path")
        if create:
            folder.mkdir(parents=True, exist_ok=True)
        return path, part, lock

    def _digest(self, path, cancel, progress, model, stage="verifying"):
        digest = hashlib.sha256()
        done = 0
        with path.open("rb") as stream:
            while True:
                _check_cancel(cancel)
                chunk = stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
                done += len(chunk)
                progress(dict(id=model["id"], stage=stage, completed=done, total=model["size_bytes"]))
        return digest

    def verify(self, identity, directory, *, cancel=None, progress=None):
        model = self._model(identity)
        cancel, progress = cancel or threading.Event(), progress or (lambda value: None)
        try:
            path, _, _ = self._paths(model, directory, create=False)
            if path.exists() and not path.is_file():
                raise SetupError("The model destination is not a regular file. Choose another model folder.", "path")
            if not path.is_file():
                return {"id": identity, "status": "missing"}
            candidates = [(model["size_bytes"], model["sha256"], "publisher")]
            candidates.extend((v["size_bytes"], v["sha256"], v.get("name", "existing variant"))
                              for v in model.get("accepted_existing_variants", []))
            size = path.stat().st_size
            matching = [entry for entry in candidates if entry[0] == size]
            if not matching:
                return {"id": identity, "status": "different"}
            digest = self._digest(path, cancel, progress, model).hexdigest()
            for _, expected, variant in matching:
                if digest == expected:
                    return {"id": identity, "status": "verified", "variant": variant}
            return {"id": identity, "status": "different"}
        except OSError as exc:
            raise SetupError("The model file could not be read. Check the folder and drive connection.", "disk") from exc

    def download(self, identity, directory, *, cancel=None, progress=None):
        model = self._model(identity)
        if not self.accepted(identity):
            raise SetupError("Read and accept this model's publisher terms before downloading.", "acceptance")
        if not model.get("download_enabled"):
            raise SetupError("This model has no enabled publisher download. Open its model card for details.", "disabled")
        cancel, progress = cancel or threading.Event(), progress or (lambda value: None)
        _check_cancel(cancel)
        try:
            path, part, lock = self._paths(model, directory, create=True)
            with _file_lock(lock):
                current = self.verify(identity, directory, cancel=cancel, progress=progress)
                if current["status"] == "verified":
                    progress(dict(id=identity, stage="verified", completed=model["size_bytes"], total=model["size_bytes"]))
                    return current
                if current["status"] == "different":
                    raise SetupError("An existing model has different contents. Keep it safe: choose another model folder or move it aside before downloading.", "existing")
                if part.exists() and not part.is_file():
                    raise SetupError("The saved download is not a regular file. Choose a different model folder.", "path")
                start = part.stat().st_size if part.exists() else 0
                if start > model["size_bytes"]:
                    part.unlink()
                    start = 0
                digest = self._digest(part, cancel, progress, model, "checking saved download") if start else hashlib.sha256()
                if start == model["size_bytes"]:
                    return self._finish(model, path, part, digest, progress)
                free = shutil.disk_usage(path.parent).free
                if free < model["size_bytes"] - start + 8 * 1024 * 1024:
                    raise SetupError("There is not enough free space for this model. Free space or choose another drive, then resume.", "space")
                headers = {"Accept-Encoding": "identity", "User-Agent": "Artegra-Enhancer-Model-Setup/1"}
                if start:
                    headers["Range"] = f"bytes={start}-"
                request = urllib.request.Request(model["download_url"], headers=headers)
                try:
                    with _open_response(request, cancel, self.allow_http_loopback) as response:
                        encoding = response.headers.get("Content-Encoding", "identity").lower()
                        if encoding not in {"", "identity"}:
                            raise SetupError("The publisher sent an encoded download. Try again later.", "response")
                        if response.status == 206:
                            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
                            if not match or int(match[1]) != start or int(match[2]) != model["size_bytes"]-1 or int(match[3]) != model["size_bytes"]:
                                raise SetupError("The publisher returned an invalid resumed download. Your saved transfer is unchanged; try again later.", "range")
                        elif response.status == 200:
                            # A server ignoring Range is safe only if we restart instead of appending.
                            start, digest = 0, hashlib.sha256()
                        else:
                            raise SetupError("The publisher did not return a model download. Try again later.", "response")
                        length = response.headers.get("Content-Length")
                        if length is not None and (not length.isdigit() or int(length) != model["size_bytes"]-start):
                            raise SetupError("The publisher's file size differs from the verified catalogue. No model was installed.", "size")
                        # If Range was ignored, a complete restart needs full-file free space too.
                        if shutil.disk_usage(path.parent).free + (part.stat().st_size if part.exists() else 0) < model["size_bytes"] - start + 8 * 1024 * 1024:
                            raise SetupError("There is not enough free space to restart this download.", "space")
                        _check_cancel(cancel)
                        with part.open("ab" if start else "wb") as output:
                            count = start
                            progress(dict(id=identity, stage="downloading", completed=count, total=model["size_bytes"]))
                            while True:
                                _check_cancel(cancel)
                                # read1 returns currently available data instead of waiting to
                                # fill a MiB while a slow peer keeps the idle timeout alive.
                                read = getattr(response, "read1", None)
                                block = (read(min(CHUNK_SIZE, model["size_bytes"]-count+1)) if read
                                         else response.read(1))
                                if not block:
                                    break
                                if count + len(block) > model["size_bytes"]:
                                    raise SetupError("The publisher sent more data than expected. No model was installed.", "size")
                                output.write(block)
                                digest.update(block)
                                count += len(block)
                                progress(dict(id=identity, stage="downloading", completed=count, total=model["size_bytes"]))
                            output.flush()
                            os.fsync(output.fileno())
                        _check_cancel(cancel)
                        if count != model["size_bytes"]:
                            raise SetupError("The connection ended early. Download again to resume the saved transfer.", "network")
                except urllib.error.HTTPError as exc:
                    message = ("The publisher requires access approval. Open the model card to review access; no account credentials are stored by the app."
                               if exc.code in {401, 403} else "The publisher is unavailable. Download again later to resume the saved transfer.")
                    raise SetupError(message, "access" if exc.code in {401, 403} else "network") from exc
                except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as exc:
                    raise SetupError("The download connection was interrupted. Check your connection, then download again to resume.", "network") from exc
                return self._finish(model, path, part, digest, progress)
        except SetupError:
            raise
        except OSError as exc:
            raise SetupError("The model could not be saved. Check free space, folder permissions and drive connection, then resume.", "disk") from exc

    def _finish(self, model, path, part, digest, progress):
        if digest.hexdigest() != model["sha256"] or part.stat().st_size != model["size_bytes"]:
            part.unlink(missing_ok=True)
            raise SetupError("The download did not match the publisher's SHA-256. The incomplete copy was removed; download again.", "integrity")
        if path.exists():
            raise SetupError("A model appeared at the destination during setup. It was left untouched.", "existing")
        # Atomic create without replacing a file another process may have created.
        try:
            os.link(part, path)
        except FileExistsError as exc:
            raise SetupError("A model appeared at the destination during setup. It was left untouched.", "existing") from exc
        except OSError as exc:
            unsupported = exc.errno in {errno.EPERM, errno.EOPNOTSUPP, errno.EXDEV, errno.ENOSYS, errno.EINVAL}
            unsupported = unsupported or getattr(exc, "winerror", None) in {1, 50, 1314}
            if os.name != "nt" or not unsupported:
                raise
            # Windows rename atomically fails when the destination exists. This also
            # supports exFAT/SMB volumes that do not implement hard links.
            try:
                os.rename(part, path)
            except FileExistsError as collision:
                raise SetupError("A model appeared at the destination during setup. It was left untouched.", "existing") from collision
        else:
            part.unlink()
        progress(dict(id=model["id"], stage="verified", completed=model["size_bytes"], total=model["size_bytes"]))
        return {"id": model["id"], "status": "verified", "variant": "publisher"}
