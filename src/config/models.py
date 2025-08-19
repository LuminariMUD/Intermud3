"""Configuration models for I3 Gateway."""


from pydantic import BaseModel, ConfigDict, Field, field_validator


class ServiceConfig(BaseModel):
    """I3 service capabilities configuration."""

    tell: int = 1
    emoteto: int = 1
    channel: int = 1
    who: int = 1
    finger: int = 1
    locate: int = 1
    chanlist_req: int = Field(1, alias="chanlist-req")
    chanlist_reply: int = Field(1, alias="chanlist-reply")
    chan_who_req: int = Field(1, alias="chan-who-req")
    chan_who_reply: int = Field(1, alias="chan-who-reply")
    auth: int = 1
    ucache: int = 1


class OOBServiceConfig(BaseModel):
    """Out-of-band service configuration."""

    mail: int = 0
    news: int = 0
    file: int = 0
    http: int = 0
    ftp: int = 0
    nntp: int = 0
    smtp: int = 0


class MudConfig(BaseModel):
    """MUD configuration."""

    name: str
    port: int
    admin_email: str
    mudlib: str = "Custom"
    base_mudlib: str = "LPMud"
    driver: str = "FluffOS"
    mud_type: str = "LP"
    open_status: str = "open"
    services: ServiceConfig = Field(default_factory=ServiceConfig)
    oob_services: OOBServiceConfig = Field(default_factory=OOBServiceConfig)


class RouterConnectionConfig(BaseModel):
    """Router connection settings."""

    timeout: int = 300
    keepalive_interval: int = 60
    reconnect_delay: int = 30
    max_reconnect_attempts: int = 10


class RouterHostConfig(BaseModel):
    """Router host configuration."""

    host: str
    port: int = 8080
    password: int = 0


class RouterConfig(BaseModel):
    """Router configuration."""

    primary: RouterHostConfig
    fallback: list[RouterHostConfig] = Field(default_factory=list)
    connection: RouterConnectionConfig = Field(default_factory=RouterConnectionConfig)


class GatewayAuthConfig(BaseModel):
    """Gateway authentication configuration."""

    enabled: bool = True
    secret: str | None = None
    token_expiry: int = 3600


class GatewayConfig(BaseModel):
    """Gateway server configuration."""

    host: str = "localhost"
    port: int = 4001
    max_packet_size: int = 65536
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 5
    max_connections: int = 100
    queue_size: int = 1000
    worker_threads: int = 4
    auth: GatewayAuthConfig = Field(default_factory=GatewayAuthConfig)


class LogComponentConfig(BaseModel):
    """Component-specific log levels."""

    network: str = "INFO"
    services: str = "INFO"
    api: str = "INFO"
    state: str = "WARNING"


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "json"
    file: str | None = None
    max_size: int = 10485760  # 10MB
    backup_count: int = 5
    components: LogComponentConfig = Field(default_factory=LogComponentConfig)


class ChannelDefinition(BaseModel):
    """Channel definition."""

    name: str
    type: int = 0  # 0 = public, 1 = private


class ChannelConfig(BaseModel):
    """Channel configuration."""

    default_channels: list[ChannelDefinition] = Field(default_factory=list)
    history_size: int = 100
    max_message_length: int = 2048


class StateConfig(BaseModel):
    """State management configuration."""

    directory: str = "state/"
    save_interval: int = 300
    backup_enabled: bool = True
    backup_count: int = 3


class MetricsConfig(BaseModel):
    """Metrics configuration."""

    enabled: bool = True
    port: int = 8080
    path: str = "/metrics"


class WebSocketConfig(BaseModel):
    """WebSocket configuration."""

    enabled: bool = True
    max_connections: int = 1000
    ping_interval: int = 30
    ping_timeout: int = 10
    max_frame_size: int = 65536
    compression: bool = True


class TCPConfig(BaseModel):
    """TCP socket configuration."""

    enabled: bool = True
    port: int = 8081
    max_connections: int = 500
    buffer_size: int = 4096


class APIKeyConfig(BaseModel):
    """API key configuration."""

    key: str
    mud_name: str
    permissions: list[str] = Field(default_factory=lambda: ["*"])
    rate_limit_override: int | None = None


class APIAuthConfig(BaseModel):
    """API authentication configuration."""

    enabled: bool = True
    require_tls: bool = False
    api_keys: list[APIKeyConfig] = Field(default_factory=list)


class RateLimitConfig(BaseModel):
    """Rate limit configuration."""

    per_minute: int = 100
    burst: int = 20


class APIRateLimitsConfig(BaseModel):
    """API rate limits configuration."""

    default: RateLimitConfig = Field(default_factory=RateLimitConfig)
    by_method: dict[str, int] = Field(default_factory=dict)


class SessionConfig(BaseModel):
    """Session management configuration."""

    timeout: int = 3600
    max_queue_size: int = 1000
    queue_ttl: int = 300
    cleanup_interval: int = 60


class APIMetricsConfig(BaseModel):
    """API metrics configuration."""

    enabled: bool = True
    export_interval: int = 60
    include_details: bool = True


class APIConfig(BaseModel):
    """API server configuration."""

    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig)
    tcp: TCPConfig = Field(default_factory=TCPConfig)
    auth: APIAuthConfig = Field(default_factory=APIAuthConfig)
    rate_limits: APIRateLimitsConfig = Field(default_factory=APIRateLimitsConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    metrics: APIMetricsConfig = Field(default_factory=APIMetricsConfig)


class DevelopmentConfig(BaseModel):
    """Development settings."""

    debug: bool = False
    reload: bool = False
    profile: bool = False


class Settings(BaseModel):
    """Main settings configuration."""

    mud: MudConfig
    router: RouterConfig
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    channels: ChannelConfig = Field(default_factory=ChannelConfig)
    state: StateConfig = Field(default_factory=StateConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    development: DevelopmentConfig = Field(default_factory=DevelopmentConfig)

    @field_validator("gateway")
    @classmethod
    def validate_gateway_auth(cls, v: GatewayConfig) -> GatewayConfig:
        """Validate gateway authentication settings."""
        if v.auth.enabled and not v.auth.secret:
            raise ValueError("Gateway auth is enabled but no secret provided")
        return v

    model_config = ConfigDict(populate_by_name=True)
