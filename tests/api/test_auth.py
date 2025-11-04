"""
Tests for authentication and authorization middleware.
"""

import time

from src.api.auth import IPFilter, RateLimitBucket


class TestRateLimitBucket:
    """Test token bucket algorithm."""

    def test_bucket_creation(self):
        """Test bucket initialization."""
        bucket = RateLimitBucket(capacity=10, tokens=10, refill_rate=1.0)
        assert bucket.capacity == 10
        assert bucket.tokens == 10
        assert bucket.refill_rate == 1.0

    def test_consume_tokens(self):
        """Test consuming tokens from bucket."""
        bucket = RateLimitBucket(capacity=10, tokens=10, refill_rate=0)  # No refill

        # Should succeed with available tokens
        assert bucket.consume(5) is True
        assert bucket.tokens == 5

        # Should fail without enough tokens
        assert bucket.consume(6) is False
        assert bucket.tokens == 5

        # Should succeed with exact tokens
        assert bucket.consume(5) is True
        assert bucket.tokens == 0

    def test_token_refill(self):
        """Test token refill over time."""
        bucket = RateLimitBucket(capacity=10, tokens=0, refill_rate=10.0)

        # Wait for refill
        time.sleep(0.5)

        # Should have refilled ~5 tokens
        assert bucket.consume(4) is True
        assert bucket.tokens < 2  # Some tokens left after consumption

    def test_bucket_reset(self):
        """Test resetting bucket to full capacity."""
        bucket = RateLimitBucket(capacity=10, tokens=3, refill_rate=1.0)
        bucket.reset()

        assert bucket.tokens == 10
        assert bucket.consume(10) is True


class TestIPFilter:
    """Test IP filtering."""

    def test_disabled_filter(self):
        """Test filter when disabled."""
        ip_filter = IPFilter({"enabled": False})

        assert ip_filter.is_allowed("192.168.1.1") is True
        assert ip_filter.is_allowed("10.0.0.1") is True
        assert ip_filter.is_allowed("invalid-ip") is True

    def test_blocklist(self):
        """Test IP blocklist."""
        ip_filter = IPFilter({"enabled": True, "blocklist": ["192.168.1.0/24", "10.0.0.1"]})

        assert ip_filter.is_allowed("192.168.1.100") is False  # In blocked range
        assert ip_filter.is_allowed("10.0.0.1") is False  # Explicitly blocked
        assert ip_filter.is_allowed("172.16.0.1") is True  # Not blocked

    def test_allowlist(self):
        """Test IP allowlist."""
        ip_filter = IPFilter({"enabled": True, "allowlist": ["192.168.1.0/24", "10.0.0.1"]})

        assert ip_filter.is_allowed("192.168.1.100") is True  # In allowed range
        assert ip_filter.is_allowed("10.0.0.1") is True  # Explicitly allowed
        assert ip_filter.is_allowed("172.16.0.1") is False  # Not in allowlist

    def test_invalid_ip(self):
        """Test handling of invalid IP addresses."""
        ip_filter = IPFilter({"enabled": True})

        assert ip_filter.is_allowed("not-an-ip") is False
        assert ip_filter.is_allowed("256.256.256.256") is False
        assert ip_filter.is_allowed("") is False
