"""Pure-Python MessagePack codec ported from lua-MessagePack 0.5.2.

Compatible with Python 3.13 on 64-bit systems. Strings are UTF-8 on the wire;
invalid UTF-8 bytes are preserved using ``surrogateescape``.
"""

from __future__ import annotations

import math
import struct
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

__all__ = [
    "Extension",
    "MessagePackError",
    "MessagePack",
    "packer",
    "VERSION",
    "DESCRIPTION",
    "COPYRIGHT",
]


VERSION = "0.5.2"
DESCRIPTION = "Pure Python implementation of lua-MessagePack 0.5.2"
COPYRIGHT = "Copyright (c) 2012-2019 Francois Perrad"

class MessagePackError(ValueError):
    """Raised when a MessagePack object is malformed or incomplete."""


@dataclass(frozen=True, slots=True)
class Extension:
    """A MessagePack extension value."""

    tag: int
    data: bytes

    def __post_init__(self) -> None:
        if not -128 <= self.tag <= 127:
            raise ValueError("extension tag must be between -128 and 127")
        if not isinstance(self.data, bytes):
            raise TypeError("extension data must be bytes")


class _Cursor:
    def __init__(
        self,
        data: bytes = b"",
        loader: Callable[[], bytes | None] | None = None,
    ) -> None:
        self.data = data
        self.position = 0
        self.loader = loader
        self.eof = loader is None

    def ensure(self, size: int, *, allow_eof: bool = False) -> bool:
        while len(self.data) - self.position < size and not self.eof:
            assert self.loader is not None
            chunk = self.loader()
            if chunk is None or chunk == b"":
                self.eof = True
                break
            if not isinstance(chunk, bytes):
                raise TypeError("byte loader must return bytes or None")
            self.data += chunk
        if len(self.data) - self.position < size:
            if allow_eof and self.position == len(self.data):
                return False
            raise MessagePackError("missing bytes")
        return True

    def read(self, size: int) -> bytes:
        self.ensure(size)
        start = self.position
        self.position += size
        return self.data[start : start + size]


class MessagePack:
    _string_mode = "string_compat"
    _array_mode = "without_hole"
    _integer_mode = "unsigned"
    _number_mode = "double"
    packers: dict[type[Any], Callable[[bytearray, Any], None]] = {}


    def set_string(self, mode: str) -> None:
        """Choose how Python strings are encoded: compat, string, or binary."""
        if mode not in {"compat", "string", "binary"}:
            raise ValueError(f"invalid option {mode!r} to set_string")
        self._string_mode = mode


    def set_array(self, mode: str) -> None:
        """Choose how dictionaries with positive integer keys are encoded."""
        if mode not in {"without_hole", "with_hole", "always_as_map"}:
            raise ValueError(f"invalid option {mode!r} to set_array")
        self._array_mode = mode


    def set_integer(self, mode: str) -> None:
        """Choose signed or unsigned integer encoding preference."""
        if mode not in {"unsigned", "signed"}:
            raise ValueError(f"invalid option {mode!r} to set_integer")
        self._integer_mode = mode


    def set_number(self, mode: str) -> None:
        """Choose float32 or float64 encoding for Python float values."""
        if mode not in {"float", "double"}:
            raise ValueError(f"invalid option {mode!r} to set_number")
        self._number_mode = mode


    def _pack_length(self, buffer: bytearray, length: int, fix_base: int, fix_max: int,
                 code8: int, code16: int, code32: int) -> None:
        if length <= fix_max:
            buffer.append(fix_base + length)
        elif code8 >= 0 and length <= 0xFF:
            buffer.extend((code8, length))
        elif length <= 0xFFFF:
            buffer.append(code16)
            buffer.extend(struct.pack(">H", length))
        elif length <= 0xFFFFFFFF:
            buffer.append(code32)
            buffer.extend(struct.pack(">I", length))
        else:
            raise OverflowError("MessagePack length exceeds 32-bit limit")


    def _pack_integer(self, buffer: bytearray, value: int) -> None:
        if self._integer_mode == "unsigned":
            if 0 <= value <= 0x7F:
                buffer.append(value)
            elif 0 <= value <= 0xFF:
                buffer.extend((0xCC, value))
            elif 0 <= value <= 0xFFFF:
                buffer.append(0xCD)
                buffer.extend(struct.pack(">H", value))
            elif 0 <= value <= 0xFFFFFFFF:
                buffer.append(0xCE)
                buffer.extend(struct.pack(">I", value))
            elif 0 <= value <= 0xFFFFFFFFFFFFFFFF:
                buffer.append(0xCF)
                buffer.extend(struct.pack(">Q", value))
            elif value >= -32:
                buffer.append(value & 0xFF)
            elif value >= -0x80:
                buffer.extend((0xD0, value & 0xFF))
            elif value >= -0x8000:
                buffer.append(0xD1)
                buffer.extend(struct.pack(">h", value))
            elif value >= -0x80000000:
                buffer.append(0xD2)
                buffer.extend(struct.pack(">i", value))
            elif value >= -0x8000000000000000:
                buffer.append(0xD3)
                buffer.extend(struct.pack(">q", value))
            else:
                raise OverflowError("integer is outside the MessagePack 64-bit range")
            return

        if 0 <= value <= 0x7F:
            buffer.append(value)
        elif 0 <= value <= 0x7FFF:
            buffer.append(0xD1)
            buffer.extend(struct.pack(">h", value))
        elif 0 <= value <= 0x7FFFFFFF:
            buffer.append(0xD2)
            buffer.extend(struct.pack(">i", value))
        elif 0 <= value <= 0x7FFFFFFFFFFFFFFF:
            buffer.append(0xD3)
            buffer.extend(struct.pack(">q", value))
        elif -32 <= value < 0:
            buffer.append(value & 0xFF)
        elif -0x80 <= value < 0:
            buffer.extend((0xD0, value & 0xFF))
        elif -0x8000 <= value < 0:
            buffer.append(0xD1)
            buffer.extend(struct.pack(">h", value))
        elif -0x80000000 <= value < 0:
            buffer.append(0xD2)
            buffer.extend(struct.pack(">i", value))
        elif -0x8000000000000000 <= value < 0:
            buffer.append(0xD3)
            buffer.extend(struct.pack(">q", value))
        else:
            raise OverflowError("integer is outside the MessagePack 64-bit range")


    def _pack_ext(self, buffer: bytearray, value: Extension) -> None:
        tag = value.tag & 0xFF
        length = len(value.data)
        fixed_codes = {1: 0xD4, 2: 0xD5, 4: 0xD6, 8: 0xD7, 16: 0xD8}
        if length in fixed_codes:
            buffer.extend((fixed_codes[length], tag))
        elif length <= 0xFF:
            buffer.extend((0xC7, length, tag))
        elif length <= 0xFFFF:
            buffer.append(0xC8)
            buffer.extend(struct.pack(">H", length))
            buffer.append(tag)
        elif length <= 0xFFFFFFFF:
            buffer.append(0xC9)
            buffer.extend(struct.pack(">I", length))
            buffer.append(tag)
        else:
            raise OverflowError("extension data exceeds 32-bit length limit")
        buffer.extend(value.data)


    def _encode(self, buffer: bytearray, value: Any) -> None:
        custom_packer = self.packers.get(type(value))
        if custom_packer is not None:
            custom_packer(buffer, value)
            return
        if value is None:
            buffer.append(0xC0)
        elif value is False:
            buffer.append(0xC2)
        elif value is True:
            buffer.append(0xC3)
        elif isinstance(value, int):
            self._pack_integer(buffer, value)
        elif isinstance(value, float):
            if math.isfinite(value) and value.is_integer() and -(2**53 - 1) < value < 2**53 - 1:
                self._pack_integer(buffer, int(value))
                return
            if self._number_mode == "float":
                buffer.append(0xCA)
                try:
                    buffer.extend(struct.pack(">f", value))
                except OverflowError:
                    buffer.extend(struct.pack(">f", math.copysign(math.inf, value)))
            else:
                buffer.append(0xCB)
                buffer.extend(struct.pack(">d", value))
        elif isinstance(value, str):
            raw = value.encode("utf-8", errors="surrogateescape")
            if self._string_mode == "binary":
                self._pack_length(buffer, len(raw), -1, -1, 0xC4, 0xC5, 0xC6)
            else:
                self._pack_length(buffer, len(raw), 0xA0, 0x1F,
                             0xD9 if self._string_mode == "string" else -1, 0xDA, 0xDB)
            buffer.extend(raw)
        elif isinstance(value, (bytes, bytearray, memoryview)):
            raw = bytes(value)
            self._pack_length(buffer, len(raw), -1, -1, 0xC4, 0xC5, 0xC6)
            buffer.extend(raw)
        elif isinstance(value, (list, tuple)):
            self._pack_length(buffer, len(value), 0x90, 0x0F, -1, 0xDC, 0xDD)
            for item in value:
                self._encode(buffer, item)
        elif isinstance(value, dict):
            self._encode_dict(buffer, value)
        elif isinstance(value, Extension):
            self._pack_ext(buffer, value)
        else:
            raise TypeError(f"unsupported MessagePack type: {type(value).__name__}")


    def _encode_dict(self, buffer: bytearray, value: dict[Any, Any]) -> None:
        if self._array_mode != "always_as_map":
            keys = list(value)
            positive_integer_keys = all(
                type(key) is int and key > 0 for key in keys
            )
            if positive_integer_keys:
                maximum = max(keys, default=0)
                if self._array_mode == "with_hole" or maximum == len(keys):
                    self._pack_length(buffer, maximum, 0x90, 0x0F, -1, 0xDC, 0xDD)
                    for index in range(1, maximum + 1):
                        self._encode(buffer, value.get(index))
                    return

        self._pack_length(buffer, len(value), 0x80, 0x0F, -1, 0xDE, 0xDF)
        for key, item in value.items():
            self._encode(buffer, key)
            self._encode(buffer, item)


    def pack(self, data: Any) -> bytes:
        """Encode one Python value as a MessagePack byte string."""
        buffer = bytearray()
        self._encode(buffer, data)
        return bytes(buffer)


    def _read_uint(self, cursor: _Cursor, size: int) -> int:
        return int.from_bytes(cursor.read(size), "big")


    def _read_int(self, cursor: _Cursor, size: int) -> int:
        return int.from_bytes(cursor.read(size), "big", signed=True)


    def _decode_string(self, cursor: _Cursor, size: int) -> str:
        return cursor.read(size).decode("utf-8", errors="surrogateescape")


    def _decode_ext(self, cursor: _Cursor, size: int, tag: int) -> Any:
        return self.build_ext(tag, cursor.read(size))


    def build_ext(self, tag: int, data: bytes) -> Any:
        """Decode an extension value; override this hook to handle application tags."""
        return None


    def _decode(self, cursor: _Cursor) -> Any:
        code = cursor.read(1)[0]
        if code <= 0x7F:
            return code
        if code >= 0xE0:
            return code - 0x100
        if 0x80 <= code <= 0x8F:
            return self._decode_map(cursor, code & 0x0F)
        if 0x90 <= code <= 0x9F:
            return [self._decode(cursor) for _ in range(code & 0x0F)]
        if 0xA0 <= code <= 0xBF:
            return self._decode_string(cursor, code & 0x1F)

        if code == 0xC0:
            return None
        if code == 0xC2:
            return False
        if code == 0xC3:
            return True
        if code in (0xC4, 0xC5, 0xC6):
            size_width = {0xC4: 1, 0xC5: 2, 0xC6: 4}[code]
            return cursor.read(self._read_uint(cursor, size_width))
        if code in (0xC7, 0xC8, 0xC9):
            size_width = {0xC7: 1, 0xC8: 2, 0xC9: 4}[code]
            size = self._read_uint(cursor, size_width)
            tag = self._read_int(cursor, 1)
            return self._decode_ext(cursor, size, tag)
        if code == 0xCA:
            return struct.unpack(">f", cursor.read(4))[0]
        if code == 0xCB:
            return struct.unpack(">d", cursor.read(8))[0]
        if code in (0xCC, 0xCD, 0xCE, 0xCF):
            size = {0xCC: 1, 0xCD: 2, 0xCE: 4, 0xCF: 8}[code]
            return self._read_uint(cursor, size)
        if code in (0xD0, 0xD1, 0xD2, 0xD3):
            size = {0xD0: 1, 0xD1: 2, 0xD2: 4, 0xD3: 8}[code]
            return self._read_int(cursor, size)
        if code in (0xD4, 0xD5, 0xD6, 0xD7, 0xD8):
            size = {0xD4: 1, 0xD5: 2, 0xD6: 4, 0xD7: 8, 0xD8: 16}[code]
            tag = self._read_int(cursor, 1)
            return self._decode_ext(cursor, size, tag)
        if code in (0xD9, 0xDA, 0xDB):
            size_width = {0xD9: 1, 0xDA: 2, 0xDB: 4}[code]
            return self._decode_string(cursor, self._read_uint(cursor, size_width))
        if code in (0xDC, 0xDD):
            size_width = 2 if code == 0xDC else 4
            return [self._decode(cursor) for _ in range(self._read_uint(cursor, size_width))]
        if code in (0xDE, 0xDF):
            size_width = 2 if code == 0xDE else 4
            return self._decode_map(cursor, self._read_uint(cursor, size_width))
        raise MessagePackError(f"unpack 0x{code:02x} is unimplemented")


    def _decode_map(self, cursor: _Cursor, size: int) -> dict[Any, Any]:
        result: dict[Any, Any] = {}
        for _ in range(size):
            key = self._decode(cursor)
            value = self._decode(cursor)
            try:
                result[key] = value
            except TypeError as exc:
                raise MessagePackError("map key is not hashable in Python") from exc
        return result


    def unpack_cursor(self, cursor: _Cursor) -> Any:
        """Decode one value from a cursor returned by the streaming decoder."""
        if not isinstance(cursor, _Cursor):
            raise TypeError("unpack_cursor expects a MessagePack cursor")
        return self._decode(cursor)


    def unpack(self, data: bytes | bytearray | memoryview) -> Any:
        """Decode exactly one MessagePack value from bytes."""
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("unpack expects bytes-like input")
        cursor = _Cursor(bytes(data))
        value = self._decode(cursor)
        if cursor.position != len(cursor.data):
            raise MessagePackError("extra bytes")
        return value


    def unpacker(
        self, source: bytes | bytearray | memoryview | Callable[[], bytes | None],
    ) -> Iterator[tuple[int, Any] | tuple[bool, Any]]:
        """Yield successive values, preserving the Lua port's offset/status tuples.

        A bytes-like source yields ``(1-based byte offset, value)`` pairs. A loader
        callback yields ``(True, value)`` pairs and returns bytes or ``None`` at EOF.
        """
        if isinstance(source, (bytes, bytearray, memoryview)):
            cursor = _Cursor(bytes(source))

            def values_from_bytes() -> Iterator[tuple[int, Any]]:
                while cursor.ensure(1, allow_eof=True):
                    offset = cursor.position + 1
                    yield offset, self._decode(cursor)

            return values_from_bytes()
        if callable(source):
            cursor = _Cursor(loader=source)

            def values_from_loader() -> Iterator[tuple[bool, Any]]:
                while cursor.ensure(1, allow_eof=True):
                    yield True, self._decode(cursor)

            return values_from_loader()
        raise TypeError("unpacker expects bytes-like input or a byte loader")

mp = MessagePack()
