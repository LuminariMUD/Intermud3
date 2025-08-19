"""LPC data structure serialization for MudMode protocol.

This module implements encoding and decoding of LPC (LPC interpreted language)
data structures used in the Intermud-3 protocol.
"""

import struct
from io import BytesIO
from typing import Any


class LPCError(Exception):
    """Base exception for LPC encoding/decoding errors."""

    pass


class LPCEncoder:
    """Encodes Python objects to LPC binary format."""

    # LPC type markers
    TYPE_STRING = 0x00
    TYPE_INTEGER = 0x01
    TYPE_ARRAY = 0x02
    TYPE_MAPPING = 0x03
    TYPE_BUFFER = 0x04
    TYPE_OBJECT = 0x05
    TYPE_FLOAT = 0x06
    TYPE_NULL = 0x07

    def encode(self, obj: Any) -> bytes:
        """Encode a Python object to LPC binary format.

        Args:
            obj: Python object to encode (str, int, list, dict, None)

        Returns:
            Encoded bytes in LPC format

        Raises:
            LPCError: If object type is not supported
        """
        buffer = BytesIO()
        self._encode_value(obj, buffer)
        return buffer.getvalue()

    def _encode_value(self, obj: Any, buffer: BytesIO) -> None:
        """Recursively encode a value to the buffer."""
        if obj is None:
            self._encode_null(buffer)
        elif isinstance(obj, str):
            self._encode_string(obj, buffer)
        elif isinstance(obj, int):
            self._encode_integer(obj, buffer)
        elif isinstance(obj, float):
            self._encode_float(obj, buffer)
        elif isinstance(obj, (list, tuple)):
            self._encode_array(obj, buffer)
        elif isinstance(obj, dict):
            self._encode_mapping(obj, buffer)
        elif isinstance(obj, bytes):
            self._encode_buffer(obj, buffer)
        else:
            raise LPCError(f"Unsupported type for LPC encoding: {type(obj)}")

    def _encode_null(self, buffer: BytesIO) -> None:
        """Encode a null value."""
        buffer.write(struct.pack("B", self.TYPE_NULL))

    def _encode_string(self, s: str, buffer: BytesIO) -> None:
        """Encode a string value."""
        buffer.write(struct.pack("B", self.TYPE_STRING))
        data = s.encode("utf-8")
        buffer.write(struct.pack(">I", len(data)))
        buffer.write(data)

    def _encode_integer(self, n: int, buffer: BytesIO) -> None:
        """Encode an integer value."""
        buffer.write(struct.pack("B", self.TYPE_INTEGER))
        # LPC uses 32-bit signed integers
        buffer.write(struct.pack(">i", n))

    def _encode_float(self, f: float, buffer: BytesIO) -> None:
        """Encode a float value."""
        buffer.write(struct.pack("B", self.TYPE_FLOAT))
        buffer.write(struct.pack(">d", f))

    def _encode_array(self, arr: list | tuple, buffer: BytesIO) -> None:
        """Encode an array/list value."""
        buffer.write(struct.pack("B", self.TYPE_ARRAY))
        buffer.write(struct.pack(">I", len(arr)))
        for item in arr:
            self._encode_value(item, buffer)

    def _encode_mapping(self, mapping: dict, buffer: BytesIO) -> None:
        """Encode a mapping/dict value."""
        buffer.write(struct.pack("B", self.TYPE_MAPPING))
        buffer.write(struct.pack(">I", len(mapping)))
        for key, value in mapping.items():
            self._encode_value(key, buffer)
            self._encode_value(value, buffer)

    def _encode_buffer(self, data: bytes, buffer: BytesIO) -> None:
        """Encode a buffer/bytes value."""
        buffer.write(struct.pack("B", self.TYPE_BUFFER))
        buffer.write(struct.pack(">I", len(data)))
        buffer.write(data)


class LPCDecoder:
    """Decodes LPC binary format to Python objects."""

    # LPC type markers (same as encoder)
    TYPE_STRING = 0x00
    TYPE_INTEGER = 0x01
    TYPE_ARRAY = 0x02
    TYPE_MAPPING = 0x03
    TYPE_BUFFER = 0x04
    TYPE_OBJECT = 0x05
    TYPE_FLOAT = 0x06
    TYPE_NULL = 0x07

    def decode(self, data: bytes) -> Any:
        """Decode LPC binary data to a Python object.

        Args:
            data: LPC encoded bytes

        Returns:
            Decoded Python object

        Raises:
            LPCError: If data is malformed or type is unsupported
        """
        buffer = BytesIO(data)
        result = self._decode_value(buffer)

        # Check if all data was consumed
        remaining = buffer.read()
        if remaining:
            raise LPCError(f"Extra data after decoding: {len(remaining)} bytes")

        return result

    def _decode_value(self, buffer: BytesIO) -> Any:
        """Recursively decode a value from the buffer."""
        type_byte = buffer.read(1)
        if not type_byte:
            raise LPCError("Unexpected end of data while reading type")

        type_code = struct.unpack("B", type_byte)[0]

        if type_code == self.TYPE_NULL:
            return None
        if type_code == self.TYPE_STRING:
            return self._decode_string(buffer)
        if type_code == self.TYPE_INTEGER:
            return self._decode_integer(buffer)
        if type_code == self.TYPE_FLOAT:
            return self._decode_float(buffer)
        if type_code == self.TYPE_ARRAY:
            return self._decode_array(buffer)
        if type_code == self.TYPE_MAPPING:
            return self._decode_mapping(buffer)
        if type_code == self.TYPE_BUFFER:
            return self._decode_buffer(buffer)
        raise LPCError(f"Unknown LPC type code: {type_code:#x}")

    def _decode_string(self, buffer: BytesIO) -> str:
        """Decode a string value."""
        length_bytes = buffer.read(4)
        if len(length_bytes) != 4:
            raise LPCError("Unexpected end of data while reading string length")

        length = struct.unpack(">I", length_bytes)[0]
        data = buffer.read(length)
        if len(data) != length:
            raise LPCError(f"Expected {length} bytes for string, got {len(data)}")

        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise LPCError(f"Invalid UTF-8 in string: {e}")

    def _decode_integer(self, buffer: BytesIO) -> int:
        """Decode an integer value."""
        int_bytes = buffer.read(4)
        if len(int_bytes) != 4:
            raise LPCError("Unexpected end of data while reading integer")

        return struct.unpack(">i", int_bytes)[0]

    def _decode_float(self, buffer: BytesIO) -> float:
        """Decode a float value."""
        float_bytes = buffer.read(8)
        if len(float_bytes) != 8:
            raise LPCError("Unexpected end of data while reading float")

        return struct.unpack(">d", float_bytes)[0]

    def _decode_array(self, buffer: BytesIO) -> list[Any]:
        """Decode an array value."""
        length_bytes = buffer.read(4)
        if len(length_bytes) != 4:
            raise LPCError("Unexpected end of data while reading array length")

        length = struct.unpack(">I", length_bytes)[0]
        result = []
        for _ in range(length):
            result.append(self._decode_value(buffer))

        return result

    def _decode_mapping(self, buffer: BytesIO) -> dict[Any, Any]:
        """Decode a mapping value."""
        length_bytes = buffer.read(4)
        if len(length_bytes) != 4:
            raise LPCError("Unexpected end of data while reading mapping length")

        length = struct.unpack(">I", length_bytes)[0]
        result = {}
        for _ in range(length):
            key = self._decode_value(buffer)
            value = self._decode_value(buffer)
            result[key] = value

        return result

    def _decode_buffer(self, buffer: BytesIO) -> bytes:
        """Decode a buffer value."""
        length_bytes = buffer.read(4)
        if len(length_bytes) != 4:
            raise LPCError("Unexpected end of data while reading buffer length")

        length = struct.unpack(">I", length_bytes)[0]
        data = buffer.read(length)
        if len(data) != length:
            raise LPCError(f"Expected {length} bytes for buffer, got {len(data)}")

        return data
