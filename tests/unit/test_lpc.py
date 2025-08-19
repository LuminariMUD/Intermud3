"""Unit tests for LPC encoder/decoder."""

import pytest
import struct
from src.network.lpc import LPCEncoder, LPCDecoder, LPCError


class TestLPCEncoder:
    """Test LPC encoding functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.encoder = LPCEncoder()
        self.decoder = LPCDecoder()
    
    def test_encode_null(self):
        """Test encoding null values."""
        encoded = self.encoder.encode(None)
        assert encoded == b'\x07'  # TYPE_NULL
        
        # Test roundtrip
        decoded = self.decoder.decode(encoded)
        assert decoded is None
    
    def test_encode_string(self):
        """Test encoding string values."""
        # Simple string
        test_str = "Hello, World!"
        encoded = self.encoder.encode(test_str)
        
        # Check type marker
        assert encoded[0] == 0x00  # TYPE_STRING
        
        # Check length
        length = struct.unpack('>I', encoded[1:5])[0]
        assert length == len(test_str.encode('utf-8'))
        
        # Test roundtrip
        decoded = self.decoder.decode(encoded)
        assert decoded == test_str
    
    def test_encode_string_unicode(self):
        """Test encoding Unicode strings."""
        test_str = "Hello 世界 🌍"
        encoded = self.encoder.encode(test_str)
        decoded = self.decoder.decode(encoded)
        assert decoded == test_str
    
    def test_encode_empty_string(self):
        """Test encoding empty string."""
        encoded = self.encoder.encode("")
        decoded = self.decoder.decode(encoded)
        assert decoded == ""
    
    def test_encode_integer(self):
        """Test encoding integer values."""
        # Positive integer
        encoded = self.encoder.encode(42)
        assert encoded[0] == 0x01  # TYPE_INTEGER
        value = struct.unpack('>i', encoded[1:5])[0]
        assert value == 42
        
        # Negative integer
        encoded = self.encoder.encode(-42)
        decoded = self.decoder.decode(encoded)
        assert decoded == -42
        
        # Zero
        encoded = self.encoder.encode(0)
        decoded = self.decoder.decode(encoded)
        assert decoded == 0
        
        # Large integers
        encoded = self.encoder.encode(2147483647)  # Max 32-bit signed
        decoded = self.decoder.decode(encoded)
        assert decoded == 2147483647
    
    def test_encode_float(self):
        """Test encoding float values."""
        test_float = 3.14159
        encoded = self.encoder.encode(test_float)
        assert encoded[0] == 0x06  # TYPE_FLOAT
        
        decoded = self.decoder.decode(encoded)
        assert abs(decoded - test_float) < 0.0001
    
    def test_encode_array(self):
        """Test encoding array/list values."""
        # Simple array
        test_array = [1, "hello", 3.14]
        encoded = self.encoder.encode(test_array)
        assert encoded[0] == 0x02  # TYPE_ARRAY
        
        # Check array length
        length = struct.unpack('>I', encoded[1:5])[0]
        assert length == 3
        
        # Test roundtrip
        decoded = self.decoder.decode(encoded)
        assert decoded == test_array
    
    def test_encode_empty_array(self):
        """Test encoding empty array."""
        encoded = self.encoder.encode([])
        decoded = self.decoder.decode(encoded)
        assert decoded == []
    
    def test_encode_nested_array(self):
        """Test encoding nested arrays."""
        test_array = [1, [2, 3], [[4, 5], 6]]
        encoded = self.encoder.encode(test_array)
        decoded = self.decoder.decode(encoded)
        assert decoded == test_array
    
    def test_encode_mapping(self):
        """Test encoding mapping/dict values."""
        test_dict = {"name": "test", "value": 42, "pi": 3.14}
        encoded = self.encoder.encode(test_dict)
        assert encoded[0] == 0x03  # TYPE_MAPPING
        
        # Check mapping size
        size = struct.unpack('>I', encoded[1:5])[0]
        assert size == 3
        
        # Test roundtrip
        decoded = self.decoder.decode(encoded)
        assert decoded == test_dict
    
    def test_encode_empty_mapping(self):
        """Test encoding empty mapping."""
        encoded = self.encoder.encode({})
        decoded = self.decoder.decode(encoded)
        assert decoded == {}
    
    def test_encode_nested_mapping(self):
        """Test encoding nested mappings."""
        test_dict = {
            "level1": {
                "level2": {
                    "value": 42
                }
            },
            "array": [1, 2, 3]
        }
        encoded = self.encoder.encode(test_dict)
        decoded = self.decoder.decode(encoded)
        assert decoded == test_dict
    
    def test_encode_buffer(self):
        """Test encoding buffer/bytes values."""
        test_bytes = b"Hello, bytes!"
        encoded = self.encoder.encode(test_bytes)
        assert encoded[0] == 0x04  # TYPE_BUFFER
        
        decoded = self.decoder.decode(encoded)
        assert decoded == test_bytes
    
    def test_encode_complex_structure(self):
        """Test encoding complex nested structure."""
        complex_data = {
            "packet_type": "tell",
            "ttl": 200,
            "originator": {
                "mud": "TestMUD",
                "user": "testuser"
            },
            "target": {
                "mud": "TargetMUD",
                "user": "targetuser"
            },
            "message": "Hello, I3!",
            "metadata": [
                {"timestamp": 1234567890},
                {"flags": ["urgent", "private"]},
                None
            ]
        }
        
        encoded = self.encoder.encode(complex_data)
        decoded = self.decoder.decode(encoded)
        assert decoded == complex_data
    
    def test_encode_unsupported_type(self):
        """Test encoding unsupported types raises error."""
        with pytest.raises(LPCError):
            self.encoder.encode(object())
        
        with pytest.raises(LPCError):
            self.encoder.encode(lambda x: x)


class TestLPCDecoder:
    """Test LPC decoding functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.encoder = LPCEncoder()
        self.decoder = LPCDecoder()
    
    def test_decode_malformed_data(self):
        """Test decoding malformed data raises error."""
        # Empty data
        with pytest.raises(LPCError):
            self.decoder.decode(b'')
        
        # Invalid type code
        with pytest.raises(LPCError):
            self.decoder.decode(b'\xFF')
        
        # Truncated string
        with pytest.raises(LPCError):
            self.decoder.decode(b'\x00\x00\x00\x00\x10')  # String with length 16 but no data
        
        # Truncated integer
        with pytest.raises(LPCError):
            self.decoder.decode(b'\x01\x00')  # Integer with only 2 bytes
    
    def test_decode_extra_data(self):
        """Test decoding with extra data raises error."""
        # Encode a simple value
        encoded = self.encoder.encode(42)
        # Add extra data
        encoded_with_extra = encoded + b'extra'
        
        with pytest.raises(LPCError, match="Extra data"):
            self.decoder.decode(encoded_with_extra)
    
    def test_decode_invalid_utf8(self):
        """Test decoding invalid UTF-8 in strings raises error."""
        # Create invalid UTF-8 string
        invalid_utf8 = b'\x00' + struct.pack('>I', 4) + b'\xff\xfe\xfd\xfc'
        
        with pytest.raises(LPCError, match="Invalid UTF-8"):
            self.decoder.decode(invalid_utf8)
    
    def test_roundtrip_all_types(self):
        """Test roundtrip encoding/decoding of all supported types."""
        test_cases = [
            None,
            "",
            "Hello, World!",
            0,
            42,
            -42,
            3.14159,
            [],
            [1, 2, 3],
            {},
            {"key": "value"},
            b"bytes",
            {
                "mixed": [
                    None,
                    42,
                    "string",
                    [1, 2, 3],
                    {"nested": True}
                ]
            }
        ]
        
        for test_data in test_cases:
            encoded = self.encoder.encode(test_data)
            decoded = self.decoder.decode(encoded)
            assert decoded == test_data


class TestLPCPerformance:
    """Performance tests for LPC encoder/decoder."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.encoder = LPCEncoder()
        self.decoder = LPCDecoder()
    
    def test_large_array_performance(self):
        """Test encoding/decoding large arrays."""
        # Create large array
        large_array = list(range(10000))
        
        # Encode
        encoded = self.encoder.encode(large_array)
        
        # Decode
        decoded = self.decoder.decode(encoded)
        
        assert decoded == large_array
    
    def test_deep_nesting_performance(self):
        """Test encoding/decoding deeply nested structures."""
        # Create deeply nested structure
        deep_structure = {"level": 0}
        current = deep_structure
        for i in range(100):
            current["nested"] = {"level": i + 1}
            current = current["nested"]
        
        # Encode
        encoded = self.encoder.encode(deep_structure)
        
        # Decode
        decoded = self.decoder.decode(encoded)
        
        assert decoded == deep_structure
    
    def test_large_string_performance(self):
        """Test encoding/decoding large strings."""
        # Create large string (1MB)
        large_string = "x" * (1024 * 1024)
        
        # Encode
        encoded = self.encoder.encode(large_string)
        
        # Decode
        decoded = self.decoder.decode(encoded)
        
        assert decoded == large_string