"""Wsclient implementation."""


import base64
import hashlib
import os
import socket
import struct
import time

GUID = b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
OP_CONT, OP_TEXT, OP_BIN, OP_CLOSE, OP_PING, OP_PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA
MAX_MESSAGE = 64 << 20


class WebSocketError(Exception):
    pass


class WebSocketClosed(WebSocketError):
    pass


def accept_key(key):
    return base64.b64encode(hashlib.sha1(key.encode('ascii') + GUID).digest()).decode('ascii')


def encode_frame(opcode, payload, mask, fin=True):
    if isinstance(payload, str):
        payload = payload.encode('utf8')
    head = bytearray([(0x80 if fin else 0) | opcode])
    n = len(payload)
    mbit = 0x80 if mask else 0
    if n < 126:
        head.append(mbit | n)
    elif n < 65536:
        head.append(mbit | 126)
        head += struct.pack('>H', n)
    else:
        head.append(mbit | 127)
        head += struct.pack('>Q', n)
    if mask:
        key = os.urandom(4)
        head += key
        payload = _apply_mask(payload, key)
    return bytes(head) + payload


def _apply_mask(data, key):
    if not data:
        return b''
    k = (key * (len(data) // 4 + 1))[:len(data)]
    return (int.from_bytes(data, 'little') ^ int.from_bytes(k, 'little')).to_bytes(len(data), 'little')


class FrameParser:
    """Incremental frame parser: feed bytes, pop complete (fin, opcode, payload) frames."""

    def __init__(self, max_message=MAX_MESSAGE):
        self.buf = bytearray()
        self.max_message = max_message

    def feed(self, data):
        self.buf += data

    def pop(self):
        b = self.buf
        if len(b) < 2:
            return None
        fin, opcode = bool(b[0] & 0x80), b[0] & 0x0F
        masked, n = bool(b[1] & 0x80), b[1] & 0x7F
        pos = 2
        if n == 126:
            if len(b) < 4:
                return None
            n = struct.unpack('>H', bytes(b[2:4]))[0]
            pos = 4
        elif n == 127:
            if len(b) < 10:
                return None
            n = struct.unpack('>Q', bytes(b[2:10]))[0]
            pos = 10
        if n > self.max_message:
            raise WebSocketError(f'frame of {n} bytes exceeds the {self.max_message} byte limit')
        key = None
        if masked:
            if len(b) < pos + 4:
                return None
            key = bytes(b[pos:pos + 4])
            pos += 4
        if len(b) < pos + n:
            return None
        payload = bytes(b[pos:pos + n])
        del b[:pos + n]
        if key:
            payload = _apply_mask(payload, key)
        return fin, opcode, payload


class WebSocket:
    def __init__(self, sock, parser, mask=True):
        self.sock = sock
        self.parser = parser
        self.mask = mask
        self.closed = False
        self.close_error = None
        self._frag_op = None
        self._frag = []

    @classmethod
    def connect(cls, host, port, path, timeout=10.0):
        sock = socket.create_connection((host, port), timeout=timeout)
        try:
            key = base64.b64encode(os.urandom(16)).decode('ascii')
            req = (f'GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                   f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n')
            sock.sendall(req.encode('ascii'))
            data = b''
            deadline = time.monotonic() + timeout
            while b'\r\n\r\n' not in data:
                if time.monotonic() > deadline:
                    raise WebSocketError('handshake timed out')
                chunk = sock.recv(4096)
                if not chunk:
                    raise WebSocketError('connection closed during the handshake')
                data += chunk
                if len(data) > 65536:
                    raise WebSocketError('handshake response too large')
            head, rest = data.split(b'\r\n\r\n', 1)
            lines = head.decode('latin-1').split('\r\n')
            if not lines[0].startswith('HTTP/1.1 101'):
                raise WebSocketError(f'handshake refused: {lines[0]}')
            hdr = {}
            for line in lines[1:]:
                if ':' in line:
                    k, v = line.split(':', 1)
                    hdr[k.strip().lower()] = v.strip()
            if hdr.get('sec-websocket-accept') != accept_key(key):
                raise WebSocketError('handshake accept key mismatch')
            parser = FrameParser()
            parser.feed(rest)
            return cls(sock, parser, mask=True)
        except BaseException:
            sock.close()
            raise

    def send_text(self, text):
        self._send(OP_TEXT, text)

    def _send(self, opcode, payload):
        if self.closed:
            raise WebSocketClosed('socket is closed')
        self.sock.sendall(encode_frame(opcode, payload, self.mask))

    def recv(self, timeout=None):
        """Next complete message (str for text, bytes for binary), or None if nothing arrived within timeout."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            frame = self.parser.pop()
            if frame is not None:
                msg = self._handle(*frame)
                if msg is not None:
                    return msg
                continue
            if self.closed:
                raise WebSocketClosed('socket is closed')
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                return None
            self.sock.settimeout(remaining)
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                return None
            if not chunk:
                self.closed = True
                raise WebSocketClosed('connection closed by the server')
            self.parser.feed(chunk)

    def _handle(self, fin, opcode, payload):
        if opcode == OP_PING:
            self._send(OP_PONG, payload)
            return None
        if opcode == OP_PONG:
            return None
        if opcode == OP_CLOSE:
            if not self.closed:
                try:
                    self.sock.sendall(encode_frame(OP_CLOSE, payload[:2], self.mask))
                except OSError as e:          
                    self.close_error = str(e)
                self.closed = True
            raise WebSocketClosed('closed by the server')
        if opcode in (OP_TEXT, OP_BIN):
            if fin:
                return payload.decode('utf8', errors='replace') if opcode == OP_TEXT else payload
            self._frag_op, self._frag = opcode, [payload]
            return None
        if opcode == OP_CONT:
            if self._frag_op is None:
                raise WebSocketError('continuation frame without a start')
            self._frag.append(payload)
            if sum(map(len, self._frag)) > MAX_MESSAGE:
                raise WebSocketError('fragmented message too large')
            if fin:
                data, op = b''.join(self._frag), self._frag_op
                self._frag_op, self._frag = None, []
                return data.decode('utf8', errors='replace') if op == OP_TEXT else data
            return None
        raise WebSocketError(f'unknown opcode {opcode}')

    def close(self):
        if not self.closed:
            try:
                self.sock.sendall(encode_frame(OP_CLOSE, struct.pack('>H', 1000), self.mask))
            except OSError as e:              
                self.close_error = str(e)
            self.closed = True
        self.sock.close()
