"""
Authentication and authorization middleware for the I3 Gateway API.

This module provides:
- API key validation
- Permission checking
- Rate limiting enforcement
- IP allowlist/blocklist
- Session token management
"""

import asyncio
import hashlib
import hmac
import ipaddress
import secrets
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

import structlog

from ..config import Settings as Config
from .session import Session

logger = structlog.get_logger(__name__)


@dataclass
class APIKey:
    """Represents an API key with associated permissions and limits."""
    
    key: str
    mud_name: str
    permissions: Set[str] = field(default_factory=set)
    rate_limit_override: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None
    disabled: bool = False
    metadata: Dict = field(default_factory=dict)


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""
    
    capacity: int
    tokens: float
    refill_rate: float
    last_refill: float = field(default_factory=time.time)
    
    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from the bucket."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Refill tokens based on elapsed time
        self.tokens = min(
            self.capacity,
            self.tokens + (elapsed * self.refill_rate)
        )
        self.last_refill = now
        
        # Check if we have enough tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def reset(self):
        """Reset the bucket to full capacity."""
        self.tokens = self.capacity
        self.last_refill = time.time()


class RateLimiter:
    """Rate limiter using token bucket algorithm."""
    
    def __init__(self, config: Dict):
        """Initialize rate limiter with configuration."""
        self.config = config
        self.buckets: Dict[str, Dict[str, RateLimitBucket]] = defaultdict(dict)
        self.cleanup_interval = config.get("cleanup_interval", 300)
        self.last_cleanup = time.time()
        
    async def check(self, session: Session, method: Optional[str] = None) -> bool:
        """Check if request is within rate limits."""
        # Periodic cleanup of old buckets
        if time.time() - self.last_cleanup > self.cleanup_interval:
            self._cleanup_buckets()
            
        # Get rate limit configuration
        limit_config = self._get_limit_config(session, method)
        if not limit_config:
            return True  # No rate limiting configured
            
        # Get or create bucket
        bucket_key = f"{session.session_id}:{method or 'global'}"
        bucket = self._get_or_create_bucket(bucket_key, limit_config)
        
        # Try to consume token
        allowed = bucket.consume()
        
        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                session_id=session.session_id,
                mud_name=session.mud_name,
                method=method
            )
            
        return allowed
    
    def _get_limit_config(self, session: Session, method: Optional[str]) -> Optional[Dict]:
        """Get rate limit configuration for session and method."""
        # Check for session-specific override
        if hasattr(session, 'rate_limit_override'):
            return {
                'per_minute': session.rate_limit_override,
                'burst': session.rate_limit_override // 3
            }
            
        # Check method-specific limits
        if method and 'by_method' in self.config:
            method_limits = self.config['by_method'].get(method)
            if method_limits:
                return {
                    'per_minute': method_limits,
                    'burst': method_limits // 3
                }
                
        # Use default limits
        return self.config.get('default')
    
    def _get_or_create_bucket(self, key: str, config: Dict) -> RateLimitBucket:
        """Get existing bucket or create new one."""
        if key not in self.buckets:
            per_minute = config['per_minute']
            burst = config.get('burst', per_minute // 3)
            
            self.buckets[key] = RateLimitBucket(
                capacity=burst,
                tokens=burst,
                refill_rate=per_minute / 60.0
            )
            
        return self.buckets[key]
    
    def _cleanup_buckets(self):
        """Remove inactive buckets to prevent memory bloat."""
        now = time.time()
        inactive_threshold = 3600  # 1 hour
        
        to_remove = []
        for key, bucket in self.buckets.items():
            if now - bucket.last_refill > inactive_threshold:
                to_remove.append(key)
                
        for key in to_remove:
            del self.buckets[key]
            
        if to_remove:
            logger.debug(
                "rate_limiter_cleanup",
                removed_count=len(to_remove)
            )
            
        self.last_cleanup = now


class IPFilter:
    """IP address filtering for allowlist/blocklist."""
    
    def __init__(self, config: Dict):
        """Initialize IP filter with configuration."""
        self.allowlist = self._parse_ip_list(config.get('allowlist', []))
        self.blocklist = self._parse_ip_list(config.get('blocklist', []))
        self.enabled = config.get('enabled', False)
        
    def is_allowed(self, ip_address: str) -> bool:
        """Check if IP address is allowed."""
        if not self.enabled:
            return True
            
        try:
            ip = ipaddress.ip_address(ip_address)
        except ValueError:
            logger.warning("invalid_ip_address", ip=ip_address)
            return False
            
        # Check blocklist first
        for network in self.blocklist:
            if ip in network:
                logger.info("ip_blocked", ip=ip_address)
                return False
                
        # If allowlist is configured, IP must be in it
        if self.allowlist:
            for network in self.allowlist:
                if ip in network:
                    return True
            logger.info("ip_not_in_allowlist", ip=ip_address)
            return False
            
        return True
    
    def _parse_ip_list(self, ip_list: List[str]) -> List[ipaddress.IPv4Network]:
        """Parse list of IP addresses/networks."""
        networks = []
        for ip_str in ip_list:
            try:
                # Handle both single IPs and CIDR notation
                if '/' not in ip_str:
                    ip_str = f"{ip_str}/32"
                networks.append(ipaddress.ip_network(ip_str))
            except ValueError:
                logger.warning("invalid_ip_network", network=ip_str)
        return networks


class AuthMiddleware:
    """Authentication middleware for API requests."""
    
    def __init__(self, config: Config):
        """Initialize authentication middleware."""
        self.config = config.api.get('auth', {})
        self.enabled = self.config.get('enabled', True)
        self.require_tls = self.config.get('require_tls', False)
        
        # Initialize components
        self.api_keys = self._load_api_keys()
        self.rate_limiter = RateLimiter(config.api.get('rate_limits', {}))
        self.ip_filter = IPFilter(config.api.get('ip_filter', {}))
        
        # Session tokens for persistent connections
        self.session_tokens: Dict[str, Tuple[str, datetime]] = {}
        self.token_ttl = timedelta(hours=self.config.get('token_ttl_hours', 24))
        
        logger.info(
            "auth_middleware_initialized",
            enabled=self.enabled,
            api_keys_count=len(self.api_keys),
            require_tls=self.require_tls
        )
    
    def _load_api_keys(self) -> Dict[str, APIKey]:
        """Load API keys from configuration."""
        keys = {}
        
        for key_config in self.config.get('api_keys', []):
            api_key = APIKey(
                key=key_config['key'],
                mud_name=key_config['mud_name'],
                permissions=set(key_config.get('permissions', ['*'])),
                rate_limit_override=key_config.get('rate_limit_override'),
                metadata=key_config.get('metadata', {})
            )
            
            # Hash the key for storage
            key_hash = self._hash_key(api_key.key)
            keys[key_hash] = api_key
            
        return keys
    
    def _hash_key(self, key: str) -> str:
        """Hash an API key for secure storage."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    async def authenticate(self, request: Dict) -> Session:
        """Authenticate an incoming request."""
        if not self.enabled:
            # Authentication disabled, create anonymous session
            return self._create_anonymous_session(request)
            
        # Check TLS requirement
        if self.require_tls and not request.get('is_tls'):
            raise AuthenticationError("TLS required for API access")
            
        # Check IP filter
        client_ip = request.get('client_ip', '')
        if not self.ip_filter.is_allowed(client_ip):
            raise AuthenticationError("IP address not allowed")
            
        # Extract authentication credentials
        api_key = self._extract_api_key(request)
        if not api_key:
            raise AuthenticationError("API key required")
            
        # Validate API key
        api_key_obj = self._validate_api_key(api_key)
        if not api_key_obj:
            raise AuthenticationError("Invalid API key")
            
        if api_key_obj.disabled:
            raise AuthenticationError("API key disabled")
            
        # Create session
        session = self._create_session(api_key_obj, request)
        
        # Check rate limits
        if not await self.rate_limiter.check(session):
            raise RateLimitError("Rate limit exceeded")
            
        # Update last used timestamp
        api_key_obj.last_used = datetime.utcnow()
        
        logger.info(
            "authentication_successful",
            mud_name=session.mud_name,
            session_id=session.session_id,
            client_ip=client_ip
        )
        
        return session
    
    def _extract_api_key(self, request: Dict) -> Optional[str]:
        """Extract API key from request."""
        # Check headers first
        headers = request.get('headers', {})
        if 'X-API-Key' in headers:
            return headers['X-API-Key']
        if 'Authorization' in headers:
            auth_header = headers['Authorization']
            if auth_header.startswith('Bearer '):
                return auth_header[7:]
                
        # Check query parameters
        params = request.get('params', {})
        if 'api_key' in params:
            return params['api_key']
            
        return None
    
    def _validate_api_key(self, key: str) -> Optional[APIKey]:
        """Validate an API key."""
        key_hash = self._hash_key(key)
        return self.api_keys.get(key_hash)
    
    def _create_session(self, api_key: APIKey, request: Dict) -> Session:
        """Create a session from an API key."""
        session = Session(
            session_id=secrets.token_urlsafe(32),
            mud_name=api_key.mud_name,
            api_key=api_key.key,
            connected_at=datetime.utcnow(),
            client_ip=request.get('client_ip', ''),
            transport_type=request.get('transport_type', 'unknown')
        )
        
        # Add permissions and rate limit override
        session.permissions = api_key.permissions
        if api_key.rate_limit_override:
            session.rate_limit_override = api_key.rate_limit_override
            
        return session
    
    def _create_anonymous_session(self, request: Dict) -> Session:
        """Create an anonymous session when auth is disabled."""
        return Session(
            session_id=secrets.token_urlsafe(32),
            mud_name="anonymous",
            api_key="",
            connected_at=datetime.utcnow(),
            client_ip=request.get('client_ip', ''),
            transport_type=request.get('transport_type', 'unknown')
        )
    
    def check_permission(self, session: Session, permission: str) -> bool:
        """Check if session has a specific permission."""
        if not self.enabled:
            return True
            
        # Check for wildcard permission
        if '*' in session.permissions:
            return True
            
        # Check specific permission
        return permission in session.permissions
    
    def create_session_token(self, session: Session) -> str:
        """Create a session token for persistent connections."""
        token = secrets.token_urlsafe(32)
        expiry = datetime.utcnow() + self.token_ttl
        
        self.session_tokens[token] = (session.session_id, expiry)
        
        logger.debug(
            "session_token_created",
            session_id=session.session_id,
            expiry=expiry.isoformat()
        )
        
        return token
    
    def validate_session_token(self, token: str) -> Optional[str]:
        """Validate a session token and return session ID."""
        if token not in self.session_tokens:
            return None
            
        session_id, expiry = self.session_tokens[token]
        
        if datetime.utcnow() > expiry:
            del self.session_tokens[token]
            logger.debug("session_token_expired", session_id=session_id)
            return None
            
        return session_id
    
    async def cleanup_expired_tokens(self):
        """Clean up expired session tokens."""
        now = datetime.utcnow()
        expired = []
        
        for token, (session_id, expiry) in self.session_tokens.items():
            if now > expiry:
                expired.append(token)
                
        for token in expired:
            del self.session_tokens[token]
            
        if expired:
            logger.debug(
                "expired_tokens_cleaned",
                count=len(expired)
            )


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when authorization fails."""
    pass


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""
    pass