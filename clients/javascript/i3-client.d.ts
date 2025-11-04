/**
 * TypeScript definitions for I3 Gateway Client Library
 */

// Connection states
export enum ConnectionState {
    DISCONNECTED = 'disconnected',
    CONNECTING = 'connecting',
    CONNECTED = 'connected',
    RECONNECTING = 'reconnecting',
    CLOSED = 'closed'
}

// Event types
export enum EventType {
    // Communication Events
    TELL_RECEIVED = 'tell_received',
    EMOTETO_RECEIVED = 'emoteto_received',
    CHANNEL_MESSAGE = 'channel_message',
    CHANNEL_EMOTE = 'channel_emote',
    
    // System Events
    MUD_ONLINE = 'mud_online',
    MUD_OFFLINE = 'mud_offline',
    CHANNEL_JOINED = 'channel_joined',
    CHANNEL_LEFT = 'channel_left',
    ERROR_OCCURRED = 'error_occurred',
    GATEWAY_RECONNECTED = 'gateway_reconnected',
    
    // User Events
    USER_JOINED_CHANNEL = 'user_joined_channel',
    USER_LEFT_CHANNEL = 'user_left_channel',
    USER_STATUS_CHANGED = 'user_status_changed',
    
    // Administrative Events
    MAINTENANCE_SCHEDULED = 'maintenance_scheduled',
    SHUTDOWN_WARNING = 'shutdown_warning',
    RATE_LIMIT_WARNING = 'rate_limit_warning',
    
    // Connection Events
    CONNECTED = 'connected',
    DISCONNECTED = 'disconnected'
}

// Configuration options
export interface I3ConfigOptions {
    url?: string;
    apiKey?: string;
    mudName?: string;
    autoReconnect?: boolean;
    reconnectInterval?: number;
    maxReconnectAttempts?: number;
    pingInterval?: number;
    pingTimeout?: number;
    queueSize?: number;
    requestTimeout?: number;
    sslVerify?: boolean;
}

// Configuration class
export class I3Config {
    url: string;
    apiKey: string;
    mudName: string;
    autoReconnect: boolean;
    reconnectInterval: number;
    maxReconnectAttempts: number;
    pingInterval: number;
    pingTimeout: number;
    queueSize: number;
    requestTimeout: number;
    sslVerify: boolean;

    constructor(options?: I3ConfigOptions);
}

// Custom error class
export class RPCError extends Error {
    code: number;
    rpcMessage: string;
    data?: any;

    constructor(code: number, message: string, data?: any);
}

// Event listener type
export type EventListener = (data: any) => void;

// User information interface
export interface UserInfo {
    name: string;
    level?: number;
    race?: string;
    guild?: string;
    idle_time?: number;
    login_time?: number;
    status?: string;
    [key: string]: any;
}

// MUD information interface
export interface MudInfo {
    name: string;
    address: string;
    port: number;
    driver: string;
    lib: string;
    status: string;
    uptime?: number;
    users?: number;
    [key: string]: any;
}

// Channel message interface
export interface ChannelMessage {
    channel: string;
    from_mud: string;
    from_user: string;
    message: string;
    timestamp: string;
    type: 'message' | 'emote';
    [key: string]: any;
}

// Filter options for who command
export interface WhoFilters {
    min_level?: number;
    max_level?: number;
    race?: string;
    guild?: string;
    [key: string]: any;
}

// Filter options for mudlist command
export interface MudlistFilters {
    status?: string;
    driver?: string;
    has_service?: string;
    [key: string]: any;
}

// Statistics interface
export interface ClientStats {
    messagesSent: number;
    messagesReceived: number;
    eventsReceived: number;
    errors: number;
    reconnects: number;
    connectedAt: string | null;
    lastActivity: string | null;
}

// Gateway status interface
export interface GatewayStatus {
    connected: boolean;
    router: string;
    uptime: number;
    services: string[];
    [key: string]: any;
}

// Gateway statistics interface
export interface GatewayStats {
    packets_sent: number;
    packets_received: number;
    connections: number;
    errors: number;
    [key: string]: any;
}

// Main client class
export class I3Client {
    config: I3Config;
    state: ConnectionState;
    
    constructor(url: string, apiKey: string, mudName: string, options?: I3ConfigOptions);
    constructor(config: I3ConfigOptions);

    // Connection methods
    connect(): Promise<void>;
    disconnect(): Promise<void>;
    isConnected(): boolean;

    // Event handling
    on(event: string, listener: EventListener): this;
    off(event: string, listener?: EventListener): this;
    once(event: string, listener: EventListener): this;
    emit(event: string, ...args: any[]): this;

    // Request methods
    sendRequest(method: string, params?: any, timeout?: number): Promise<any>;

    // Communication methods
    tell(targetMud: string, targetUser: string, message: string, fromUser?: string): Promise<any>;
    emoteto(targetMud: string, targetUser: string, message: string, fromUser?: string): Promise<any>;
    channelSend(channel: string, message: string, fromUser?: string): Promise<any>;
    channelEmote(channel: string, message: string, fromUser?: string): Promise<any>;

    // Information methods
    who(targetMud: string, filters?: WhoFilters): Promise<UserInfo[]>;
    finger(targetMud: string, targetUser: string): Promise<UserInfo>;
    locate(targetUser: string): Promise<MudInfo[]>;
    mudlist(refresh?: boolean, filter?: MudlistFilters): Promise<MudInfo[]>;

    // Channel management
    channelJoin(channel: string, listenOnly?: boolean): Promise<any>;
    channelLeave(channel: string): Promise<any>;
    channelList(): Promise<string[]>;
    channelWho(channel: string): Promise<UserInfo[]>;
    channelHistory(channel: string, limit?: number): Promise<ChannelMessage[]>;

    // Administrative methods
    status(): Promise<GatewayStatus>;
    getStats(): Promise<GatewayStats>;
    ping(): Promise<number>;
    reconnectRouter(): Promise<any>;

    // Utility methods
    getClientStats(): ClientStats;
    getSubscribedChannels(): string[];
    waitClosed(): Promise<void>;
}

// Callback-based client
export type CallbackFunction<T = any> = (error: Error | null, result?: T) => void;

export class CallbackI3Client {
    client: I3Client;

    constructor(url: string, apiKey: string, mudName: string, options?: I3ConfigOptions);

    // Connection methods
    connect(callback: CallbackFunction<void>): void;
    disconnect(callback: CallbackFunction<void>): void;
    isConnected(): boolean;

    // Event handling (proxied from main client)
    on(event: string, listener: EventListener): this;
    off(event: string, listener?: EventListener): this;
    emit(event: string, ...args: any[]): this;

    // Communication methods
    tell(targetMud: string, targetUser: string, message: string, callback: CallbackFunction): void;
    tell(targetMud: string, targetUser: string, message: string, fromUser: string, callback: CallbackFunction): void;
    
    channelSend(channel: string, message: string, callback: CallbackFunction): void;
    channelSend(channel: string, message: string, fromUser: string, callback: CallbackFunction): void;

    // Information methods
    who(targetMud: string, callback: CallbackFunction<UserInfo[]>): void;
    who(targetMud: string, filters: WhoFilters, callback: CallbackFunction<UserInfo[]>): void;
    
    mudlist(callback: CallbackFunction<MudInfo[]>): void;
    mudlist(refresh: boolean, callback: CallbackFunction<MudInfo[]>): void;
    mudlist(refresh: boolean, filter: MudlistFilters, callback: CallbackFunction<MudInfo[]>): void;

    // Utility methods
    getStats(): ClientStats;
}

// Factory functions
export function createClient(url: string, apiKey: string, mudName: string, options?: I3ConfigOptions): I3Client;
export function createCallbackClient(url: string, apiKey: string, mudName: string, options?: I3ConfigOptions): CallbackI3Client;

// Default export
export default I3Client;