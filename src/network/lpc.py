"""LPC data structure serialization for MudMode protocol.

This module implements encoding and decoding of LPC (LPC interpreted language)
data structures used in the Intermud-3 protocol.

MudMode uses TEXT-based LPC serialization format:
- Arrays: ({"element1","element2",123,})
- Mappings: (["key":"value","key2":123,])
- Strings: "text with \"escapes\""
- Integers: 123
- Null/0: 0 (zero integer)

Reference: https://wotf.org/specs/mudmode.html
"""

import struct
from io import BytesIO
from typing import Any


class LPCError(Exception):
    """Base exception for LPC encoding/decoding errors."""


class LPCEncoder:
    """Encodes Python objects to LPC text format for MudMode protocol.

    MudMode uses a text-based serialization format similar to JSON but
    based on LPC literals. This encoder produces text output that can
    be sent over MudMode connections.
    """

    def encode(self, obj: Any) -> bytes:
        """Encode a Python object to LPC text format.

        Args:
            obj: Python object to encode (str, int, list, dict, None)

        Returns:
            Encoded bytes in LPC text format (UTF-8)

        Raises:
            LPCError: If object type is not supported
        """
        text = self._encode_value(obj)
        return text.encode("utf-8")

    def _encode_value(self, obj: Any) -> str:
        """Recursively encode a value to text."""
        if obj is None:
            return "0"
        elif isinstance(obj, bool):
            return "1" if obj else "0"
        elif isinstance(obj, int):
            return str(obj)
        elif isinstance(obj, float):
            return str(obj)
        elif isinstance(obj, str):
            return self._encode_string(obj)
        elif isinstance(obj, (list, tuple)):
            return self._encode_array(obj)
        elif isinstance(obj, dict):
            return self._encode_mapping(obj)
        elif isinstance(obj, bytes):
            # Encode bytes as a string
            return self._encode_string(obj.decode("utf-8", errors="replace"))
        else:
            raise LPCError(f"Unsupported type for LPC encoding: {type(obj)}")

    def _encode_string(self, s: str) -> str:
        """Encode a string value with proper escaping."""
        # Escape backslashes first, then quotes
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _encode_array(self, arr: list | tuple) -> str:
        """Encode an array/list value."""
        elements = [self._encode_value(item) for item in arr]
        # LPC arrays: ({"elem1","elem2",})
        return "({" + ",".join(elements) + ",})"

    def _encode_mapping(self, mapping: dict) -> str:
        """Encode a mapping/dict value."""
        pairs = []
        for key, value in mapping.items():
            encoded_key = self._encode_value(key)
            encoded_value = self._encode_value(value)
            pairs.append(f"{encoded_key}:{encoded_value}")
        # LPC mappings: (["key":"value",])
        return "([" + ",".join(pairs) + ",])"


class LPCDecoder:
    """Decodes LPC text format to Python objects.

    MudMode uses text-based LPC format:
    - Arrays: ({"element1","element2",123,})
    - Mappings: (["key":"value",])
    - Strings: "text"
    - Integers: 123 or -123
    - Floats: 1.23
    """

    def __init__(self):
        self._text = ""
        self._pos = 0

    def decode(self, data: bytes) -> Any:
        """Decode LPC text data to a Python object.

        Args:
            data: LPC encoded bytes (UTF-8 text)

        Returns:
            Decoded Python object

        Raises:
            LPCError: If data is malformed
        """
        # Strip trailing NUL if present
        if data.endswith(b"\x00"):
            data = data[:-1]

        try:
            self._text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise LPCError(f"Invalid UTF-8 in LPC data: {e}")

        self._pos = 0
        result = self._decode_value()

        # Check for trailing data (skip whitespace)
        self._skip_whitespace()
        if self._pos < len(self._text):
            pass  # Allow trailing data for partial packets

        return result

    def _peek(self) -> str | None:
        """Peek at current character without consuming."""
        if self._pos >= len(self._text):
            return None
        return self._text[self._pos]

    def _advance(self) -> str:
        """Consume and return current character."""
        if self._pos >= len(self._text):
            raise LPCError("Unexpected end of data")
        ch = self._text[self._pos]
        self._pos += 1
        return ch

    def _skip_whitespace(self):
        """Skip whitespace characters."""
        while self._pos < len(self._text) and self._text[self._pos] in " \t\n\r":
            self._pos += 1

    def _decode_value(self) -> Any:
        """Decode a single value."""
        self._skip_whitespace()

        ch = self._peek()
        if ch is None:
            raise LPCError("Unexpected end of data")

        if ch == '"':
            return self._decode_string()
        elif ch == '(':
            return self._decode_compound()
        elif ch == '-' or ch.isdigit():
            return self._decode_number()
        else:
            raise LPCError(f"Unexpected character: {ch!r} at position {self._pos}")

    def _decode_string(self) -> str:
        """Decode a quoted string."""
        if self._advance() != '"':
            raise LPCError("Expected opening quote")

        result = []
        while True:
            ch = self._advance()
            if ch == '"':
                break
            elif ch == '\\':
                # Escape sequence
                next_ch = self._advance()
                if next_ch == '"':
                    result.append('"')
                elif next_ch == '\\':
                    result.append('\\')
                elif next_ch == 'n':
                    result.append('\n')
                elif next_ch == 't':
                    result.append('\t')
                elif next_ch == 'r':
                    result.append('\r')
                else:
                    result.append(next_ch)
            else:
                result.append(ch)

        return ''.join(result)

    def _decode_number(self) -> int | float:
        """Decode a number (integer or float)."""
        start = self._pos

        # Handle negative
        if self._peek() == '-':
            self._advance()

        # Read digits
        while self._peek() and (self._peek().isdigit() or self._peek() == '.'):
            self._advance()

        num_str = self._text[start:self._pos]

        if '.' in num_str:
            return float(num_str)
        return int(num_str)

    def _decode_compound(self) -> list | dict:
        """Decode an array or mapping."""
        if self._advance() != '(':
            raise LPCError("Expected '('")

        ch = self._advance()
        if ch == '{':
            return self._decode_array()
        elif ch == '[':
            return self._decode_mapping()
        else:
            raise LPCError(f"Expected '{{' or '[' after '(', got {ch!r}")

    def _decode_array(self) -> list:
        """Decode an array: ({"elem1","elem2",})"""
        result = []

        while True:
            self._skip_whitespace()
            ch = self._peek()

            if ch == ',':
                self._advance()
                continue
            elif ch == '}':
                self._advance()
                break
            else:
                result.append(self._decode_value())

        # Consume closing )
        self._skip_whitespace()
        if self._peek() == ')':
            self._advance()

        return result

    def _decode_mapping(self) -> dict:
        """Decode a mapping: (["key":"value",])"""
        result = {}

        while True:
            self._skip_whitespace()
            ch = self._peek()

            if ch == ',':
                self._advance()
                continue
            elif ch == ']':
                self._advance()
                break
            else:
                key = self._decode_value()
                self._skip_whitespace()
                if self._peek() == ':':
                    self._advance()
                value = self._decode_value()
                result[key] = value

        # Consume closing )
        self._skip_whitespace()
        if self._peek() == ')':
            self._advance()

        return result
