/**
 * Intermud3 Gateway Client Library for JavaScript/Node.js
 * 
 * A comprehensive JavaScript client library for connecting to the Intermud3 Gateway API.
 * Provides both Promise-based and callback interfaces for MUD integration.
 * Works in both Node.js and browser environments.
 * 
 * @author Intermud3 Gateway Project
 * @version 1.0.0
 * @license MIT
 */

// Environment detection
const isNode = typeof process !== 'undefined' && process.versions && process.versions.node;
const isBrowser = typeof window !== 'undefined' && typeof window.document !== 'undefined';

// Import WebSocket implementation based on environment
let WebSocket;
if (isNode) {
    try {
        WebSocket = require('ws');
    } catch (e) {
        throw new Error('WebSocket library not found. Please install: npm install ws');
    }
} else if (isBrowser) {
    WebSocket = window.WebSocket || window.MozWebSocket;
    if (!WebSocket) {
        throw new Error('WebSocket not supported in this browser');
    }
}

// Connection states
const ConnectionState = {
    DISCONNECTED: 'disconnected',
    CONNECTING: 'connecting', 
    CONNECTED: 'connected',
    RECONNECTING: 'reconnecting',
    CLOSED: 'closed'
};

// Event types for better type safety
const EventType = {
    // Communication Events
    TELL_RECEIVED: 'tell_received',
    EMOTETO_RECEIVED: 'emoteto_received',
    CHANNEL_MESSAGE: 'channel_message',
    CHANNEL_EMOTE: 'channel_emote',
    
    // System Events
    MUD_ONLINE: 'mud_online',
    MUD_OFFLINE: 'mud_offline',
    CHANNEL_JOINED: 'channel_joined',
    CHANNEL_LEFT: 'channel_left',
    ERROR_OCCURRED: 'error_occurred',
    GATEWAY_RECONNECTED: 'gateway_reconnected',
    
    // User Events
    USER_JOINED_CHANNEL: 'user_joined_channel',
    USER_LEFT_CHANNEL: 'user_left_channel',
    USER_STATUS_CHANGED: 'user_status_changed',
    
    // Administrative Events
    MAINTENANCE_SCHEDULED: 'maintenance_scheduled',
    SHUTDOWN_WARNING: 'shutdown_warning',
    RATE_LIMIT_WARNING: 'rate_limit_warning',
    
    // Connection Events
    CONNECTED: 'connected',
    DISCONNECTED: 'disconnected'
};

/**
 * Custom error class for JSON-RPC errors
 */
class RPCError extends Error {
    constructor(code, message, data = null) {
        super(`RPC Error ${code}: ${message}`);
        this.name = 'RPCError';
        this.code = code;
        this.rpcMessage = message;
        this.data = data;
    }
}

/**
 * Configuration class for I3 client
 */
class I3Config {
    constructor(options = {}) {
        this.url = options.url || 'ws://localhost:8080';
        this.apiKey = options.apiKey || '';
        this.mudName = options.mudName || '';
        this.autoReconnect = options.autoReconnect !== false;
        this.reconnectInterval = options.reconnectInterval || 5000; // ms
        this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
        this.pingInterval = options.pingInterval || 30000; // ms
        this.pingTimeout = options.pingTimeout || 10000; // ms
        this.queueSize = options.queueSize || 1000;
        this.requestTimeout = options.requestTimeout || 30000; // ms
        this.sslVerify = options.sslVerify !== false;
    }
}

/**
 * Pending request tracking
 */
class PendingRequest {
    constructor(id, method, params) {
        this.id = id;
        this.method = method;
        this.params = params;
        this.timestamp = Date.now();
        this.promise = new Promise((resolve, reject) => {
            this.resolve = resolve;
            this.reject = reject;
        });
    }
}

/**
 * Event emitter implementation for cross-platform compatibility
 */
class EventEmitter {
    constructor() {
        this.events = {};
    }

    on(event, listener) {
        if (!this.events[event]) {
            this.events[event] = [];
        }
        this.events[event].push(listener);
        return this;
    }

    off(event, listener) {
        if (!this.events[event]) return this;
        
        if (!listener) {
            delete this.events[event];
            return this;
        }
        
        const index = this.events[event].indexOf(listener);
        if (index > -1) {
            this.events[event].splice(index, 1);
        }
        return this;
    }

    emit(event, ...args) {
        if (!this.events[event]) return this;
        
        this.events[event].forEach(listener => {
            try {
                listener.apply(this, args);
            } catch (error) {
                console.error(`Error in event listener for ${event}:`, error);
            }
        });
        return this;
    }

    once(event, listener) {
        const onceWrapper = (...args) => {
            this.off(event, onceWrapper);
            listener.apply(this, args);
        };
        return this.on(event, onceWrapper);
    }
}

/**
 * Main I3 Client class
 */
class I3Client extends EventEmitter {
    /**
     * Initialize I3 client
     * 
     * @param {string|object} url - Gateway WebSocket URL or config object
     * @param {string} apiKey - API authentication credential 
     * @param {string} mudName - Your MUD's name
     * @param {object} options - Additional configuration options
     */
    constructor(url, apiKey, mudName, options = {}) {
        super();
        
        // Handle constructor overloading
        if (typeof url === 'object') {
            // Single config object
            this.config = new I3Config(url);
        } else {
            // Separate parameters
            this.config = new I3Config({
                url,
                apiKey,
                mudName,
                ...options
            });
        }

        // Validate required parameters
        if (!this.config.url) {
            throw new Error('URL is required');
        }
        if (!this.config.apiKey) {
            throw new Error('API key is required');
        }
        if (!this.config.mudName) {
            throw new Error('MUD name is required');
        }

        // Connection state
        this.state = ConnectionState.DISCONNECTED;
        this.websocket = null;
        this.reconnectAttempts = 0;
        this.closing = false;

        // Request tracking
        this.pendingRequests = new Map();
        this.requestCounter = 0;

        // Subscriptions
        this.subscribedChannels = new Set();

        // Timers
        this.reconnectTimer = null;
        this.pingTimer = null;

        // Statistics
        this.stats = {
            messagesSent: 0,
            messagesReceived: 0,
            eventsReceived: 0,
            errors: 0,
            reconnects: 0,
            connectedAt: null,
            lastActivity: null
        };
    }

    /**
     * Connect to the I3 Gateway
     * @returns {Promise<void>}
     */
    async connect() {
        if (this.state !== ConnectionState.DISCONNECTED) {
            throw new Error(`Cannot connect in state ${this.state}`);
        }

        this.state = ConnectionState.CONNECTING;
        this.closing = false;

        return new Promise((resolve, reject) => {
            try {
                // Prepare headers
                const headers = {
                    'X-API-Key': this.config.apiKey,
                    'X-MUD-Name': this.config.mudName
                };

                // Create WebSocket connection
                const wsOptions = isNode ? { headers } : undefined;
                this.websocket = new WebSocket(this.config.url, wsOptions);

                // Set up event handlers
                this.websocket.onopen = () => {
                    this.state = ConnectionState.CONNECTED;
                    this.reconnectAttempts = 0;
                    this.stats.connectedAt = new Date().toISOString();

                    // Start ping timer
                    this.startPingTimer();

                    // Emit connected event
                    this.emit(EventType.CONNECTED, {});
                    
                    console.log(`Connected to I3 Gateway at ${this.config.url}`);
                    resolve();
                };

                this.websocket.onmessage = (event) => {
                    this.handleMessage(event.data);
                };

                this.websocket.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    this.stats.errors++;
                    
                    if (this.state === ConnectionState.CONNECTING) {
                        reject(new Error(`Failed to connect: ${error.message || 'Unknown error'}`));
                    }
                };

                this.websocket.onclose = (event) => {
                    console.log('WebSocket closed:', event.code, event.reason);
                    this.handleDisconnect();
                };

            } catch (error) {
                this.state = ConnectionState.DISCONNECTED;
                reject(new Error(`Failed to connect: ${error.message}`));
            }
        });
    }

    /**
     * Disconnect from the I3 Gateway
     * @returns {Promise<void>}
     */
    async disconnect() {
        this.closing = true;
        this.state = ConnectionState.CLOSED;

        // Clear timers
        this.clearTimers();

        // Reject pending requests
        this.pendingRequests.forEach(request => {
            request.reject(new Error('Connection closed'));
        });
        this.pendingRequests.clear();

        // Close WebSocket
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }

        // Emit disconnected event
        this.emit(EventType.DISCONNECTED, {});
        
        console.log('Disconnected from I3 Gateway');
    }

    /**
     * Handle WebSocket disconnect
     */
    handleDisconnect() {
        this.clearTimers();
        
        if (this.state !== ConnectionState.CLOSED) {
            this.state = ConnectionState.DISCONNECTED;
            this.emit(EventType.DISCONNECTED, {});
        }

        // Handle reconnection
        if (this.config.autoReconnect && !this.closing) {
            this.attemptReconnect();
        }
    }

    /**
     * Attempt to reconnect to gateway
     */
    async attemptReconnect() {
        if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            await this.disconnect();
            return;
        }

        this.state = ConnectionState.RECONNECTING;
        this.reconnectAttempts++;
        this.stats.reconnects++;

        console.log(`Reconnecting (attempt ${this.reconnectAttempts}/${this.config.maxReconnectAttempts})`);

        // Wait before reconnecting
        const delay = this.config.reconnectInterval * this.reconnectAttempts;
        this.reconnectTimer = setTimeout(async () => {
            try {
                this.state = ConnectionState.DISCONNECTED;
                await this.connect();

                // Restore subscriptions
                for (const channel of this.subscribedChannels) {
                    await this.channelJoin(channel);
                }
            } catch (error) {
                console.error('Reconnection failed:', error);
                this.attemptReconnect();
            }
        }, delay);
    }

    /**
     * Start ping timer
     */
    startPingTimer() {
        this.pingTimer = setInterval(async () => {
            try {
                if (this.isConnected()) {
                    await this.ping();
                }
            } catch (error) {
                console.error('Ping failed:', error);
            }
        }, this.config.pingInterval);
    }

    /**
     * Clear all timers
     */
    clearTimers() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.pingTimer) {
            clearInterval(this.pingTimer);
            this.pingTimer = null;
        }
    }

    /**
     * Handle incoming message from gateway
     * @param {string} data - Raw message data
     */
    handleMessage(data) {
        try {
            const message = JSON.parse(data);
            this.stats.messagesReceived++;
            this.stats.lastActivity = new Date().toISOString();

            // Check if it's a response or event
            if ('id' in message) {
                // Response to our request
                this.handleResponse(message);
            } else {
                // Event from gateway
                this.handleEvent(message);
            }
        } catch (error) {
            console.error('Invalid JSON received:', error);
            this.stats.errors++;
        }
    }

    /**
     * Handle RPC response
     * @param {object} message - Response message
     */
    handleResponse(message) {
        const requestId = message.id;
        const pending = this.pendingRequests.get(requestId);
        
        if (!pending) {
            console.warn(`Received response for unknown request: ${requestId}`);
            return;
        }

        this.pendingRequests.delete(requestId);

        if (message.error) {
            // Error response
            const error = message.error;
            const rpcError = new RPCError(
                error.code || -1,
                error.message || 'Unknown error',
                error.data
            );
            pending.reject(rpcError);
        } else {
            // Success response
            pending.resolve(message.result);
        }
    }

    /**
     * Handle incoming event
     * @param {object} message - Event message
     */
    handleEvent(message) {
        const method = message.method;
        const params = message.params || {};

        if (!method) {
            console.warn('Received event without method');
            return;
        }

        this.stats.eventsReceived++;
        this.emit(method, params);
    }

    /**
     * Send a JSON-RPC request to the gateway
     * @param {string} method - RPC method name
     * @param {object} params - Method parameters
     * @param {number} timeout - Request timeout in milliseconds
     * @returns {Promise<any>} Response result
     */
    async sendRequest(method, params = {}, timeout = null) {
        if (this.state !== ConnectionState.CONNECTED) {
            throw new Error(`Not connected (state: ${this.state})`);
        }

        // Generate request ID
        this.requestCounter++;
        const requestId = `${this.config.mudName}-${this.requestCounter}-${Math.random().toString(36).substr(2, 8)}`;

        // Create request
        const request = {
            jsonrpc: '2.0',
            id: requestId,
            method: method,
            params: params
        };

        // Track pending request
        const pending = new PendingRequest(requestId, method, params);
        this.pendingRequests.set(requestId, pending);

        // Set up timeout
        const timeoutMs = timeout || this.config.requestTimeout;
        const timeoutTimer = setTimeout(() => {
            this.pendingRequests.delete(requestId);
            pending.reject(new Error(`Request timeout after ${timeoutMs}ms`));
        }, timeoutMs);

        try {
            // Send request
            this.websocket.send(JSON.stringify(request));
            this.stats.messagesSent++;

            // Wait for response
            const result = await pending.promise;
            clearTimeout(timeoutTimer);
            return result;
        } catch (error) {
            clearTimeout(timeoutTimer);
            this.pendingRequests.delete(requestId);
            throw error;
        }
    }

    // Communication methods

    /**
     * Send a tell to a user on another MUD
     * @param {string} targetMud - Target MUD name
     * @param {string} targetUser - Target username
     * @param {string} message - Message to send
     * @param {string} fromUser - Optional sender name
     * @returns {Promise<object>} Response from gateway
     */
    async tell(targetMud, targetUser, message, fromUser = null) {
        const params = {
            target_mud: targetMud,
            target_user: targetUser,
            message: message
        };
        if (fromUser) {
            params.from_user = fromUser;
        }
        return await this.sendRequest('tell', params);
    }

    /**
     * Send an emote to a user on another MUD
     * @param {string} targetMud - Target MUD name
     * @param {string} targetUser - Target username
     * @param {string} message - Emote message
     * @param {string} fromUser - Optional sender name
     * @returns {Promise<object>} Response from gateway
     */
    async emoteto(targetMud, targetUser, message, fromUser = null) {
        const params = {
            target_mud: targetMud,
            target_user: targetUser,
            message: message
        };
        if (fromUser) {
            params.from_user = fromUser;
        }
        return await this.sendRequest('emoteto', params);
    }

    /**
     * Send a message to a channel
     * @param {string} channel - Channel name
     * @param {string} message - Message to send
     * @param {string} fromUser - Optional sender name
     * @returns {Promise<object>} Response from gateway
     */
    async channelSend(channel, message, fromUser = null) {
        const params = {
            channel: channel,
            message: message
        };
        if (fromUser) {
            params.from_user = fromUser;
        }
        return await this.sendRequest('channel_send', params);
    }

    /**
     * Send an emote to a channel
     * @param {string} channel - Channel name
     * @param {string} message - Emote message
     * @param {string} fromUser - Optional sender name
     * @returns {Promise<object>} Response from gateway
     */
    async channelEmote(channel, message, fromUser = null) {
        const params = {
            channel: channel,
            message: message
        };
        if (fromUser) {
            params.from_user = fromUser;
        }
        return await this.sendRequest('channel_emote', params);
    }

    // Information methods

    /**
     * Get list of users on a MUD
     * @param {string} targetMud - Target MUD name
     * @param {object} filters - Optional filters (min_level, max_level, race, guild)
     * @returns {Promise<Array>} List of user information
     */
    async who(targetMud, filters = null) {
        const params = { target_mud: targetMud };
        if (filters) {
            params.filters = filters;
        }
        const result = await this.sendRequest('who', params);
        return result.users || [];
    }

    /**
     * Get detailed information about a user
     * @param {string} targetMud - Target MUD name
     * @param {string} targetUser - Target username
     * @returns {Promise<object>} User information
     */
    async finger(targetMud, targetUser) {
        const params = {
            target_mud: targetMud,
            target_user: targetUser
        };
        return await this.sendRequest('finger', params);
    }

    /**
     * Locate a user on the network
     * @param {string} targetUser - Username to search for
     * @returns {Promise<Array>} List of MUDs where user was found
     */
    async locate(targetUser) {
        const result = await this.sendRequest('locate', { target_user: targetUser });
        return result.locations || [];
    }

    /**
     * Get list of MUDs on the network
     * @param {boolean} refresh - Force refresh from router
     * @param {object} filter - Optional filters (status, driver, has_service)
     * @returns {Promise<Array>} List of MUD information
     */
    async mudlist(refresh = false, filter = null) {
        const params = { refresh: refresh };
        if (filter) {
            params.filter = filter;
        }
        const result = await this.sendRequest('mudlist', params);
        return result.muds || [];
    }

    // Channel management

    /**
     * Join a channel
     * @param {string} channel - Channel name
     * @param {boolean} listenOnly - If true, can only receive messages
     * @returns {Promise<object>} Response from gateway
     */
    async channelJoin(channel, listenOnly = false) {
        const params = {
            channel: channel,
            listen_only: listenOnly
        };
        const result = await this.sendRequest('channel_join', params);
        this.subscribedChannels.add(channel);
        return result;
    }

    /**
     * Leave a channel
     * @param {string} channel - Channel name
     * @returns {Promise<object>} Response from gateway
     */
    async channelLeave(channel) {
        const result = await this.sendRequest('channel_leave', { channel: channel });
        this.subscribedChannels.delete(channel);
        return result;
    }

    /**
     * Get list of available channels
     * @returns {Promise<Array>} List of channel names
     */
    async channelList() {
        const result = await this.sendRequest('channel_list', {});
        return result.channels || [];
    }

    /**
     * Get list of users on a channel
     * @param {string} channel - Channel name
     * @returns {Promise<Array>} List of users on the channel
     */
    async channelWho(channel) {
        const result = await this.sendRequest('channel_who', { channel: channel });
        return result.users || [];
    }

    /**
     * Get channel message history
     * @param {string} channel - Channel name
     * @param {number} limit - Maximum number of messages to retrieve
     * @returns {Promise<Array>} List of historical messages
     */
    async channelHistory(channel, limit = 100) {
        const params = {
            channel: channel,
            limit: limit
        };
        const result = await this.sendRequest('channel_history', params);
        return result.messages || [];
    }

    // Administrative methods

    /**
     * Get gateway connection status
     * @returns {Promise<object>} Status information
     */
    async status() {
        return await this.sendRequest('status', {});
    }

    /**
     * Get gateway statistics
     * @returns {Promise<object>} Statistics information
     */
    async getStats() {
        return await this.sendRequest('stats', {});
    }

    /**
     * Ping the gateway
     * @returns {Promise<number>} Round-trip time in milliseconds
     */
    async ping() {
        const start = Date.now();
        await this.sendRequest('ping', {});
        return Date.now() - start;
    }

    /**
     * Force gateway to reconnect to I3 router
     * @returns {Promise<object>} Response from gateway
     */
    async reconnectRouter() {
        return await this.sendRequest('reconnect', {});
    }

    // Utility methods

    /**
     * Check if client is connected
     * @returns {boolean} True if connected
     */
    isConnected() {
        return this.state === ConnectionState.CONNECTED;
    }

    /**
     * Get client statistics
     * @returns {object} Statistics object
     */
    getClientStats() {
        return { ...this.stats };
    }

    /**
     * Get list of subscribed channels
     * @returns {Array} Array of subscribed channel names
     */
    getSubscribedChannels() {
        return Array.from(this.subscribedChannels);
    }

    /**
     * Wait until the connection is closed
     * @returns {Promise<void>}
     */
    async waitClosed() {
        return new Promise((resolve) => {
            if (this.state === ConnectionState.CLOSED) {
                resolve();
                return;
            }
            this.once(EventType.DISCONNECTED, resolve);
        });
    }
}

// Callback-based wrapper for compatibility
class CallbackI3Client {
    constructor(url, apiKey, mudName, options = {}) {
        this.client = new I3Client(url, apiKey, mudName, options);
        
        // Forward events
        this.client.on = this.client.on.bind(this.client);
        this.client.off = this.client.off.bind(this.client);
        this.client.emit = this.client.emit.bind(this.client);
    }

    connect(callback) {
        this.client.connect()
            .then(() => callback(null))
            .catch(callback);
    }

    disconnect(callback) {
        this.client.disconnect()
            .then(() => callback(null))
            .catch(callback);
    }

    tell(targetMud, targetUser, message, fromUser, callback) {
        if (typeof fromUser === 'function') {
            callback = fromUser;
            fromUser = null;
        }
        this.client.tell(targetMud, targetUser, message, fromUser)
            .then(result => callback(null, result))
            .catch(callback);
    }

    channelSend(channel, message, fromUser, callback) {
        if (typeof fromUser === 'function') {
            callback = fromUser;
            fromUser = null;
        }
        this.client.channelSend(channel, message, fromUser)
            .then(result => callback(null, result))
            .catch(callback);
    }

    who(targetMud, filters, callback) {
        if (typeof filters === 'function') {
            callback = filters;
            filters = null;
        }
        this.client.who(targetMud, filters)
            .then(result => callback(null, result))
            .catch(callback);
    }

    mudlist(refresh, filter, callback) {
        if (typeof refresh === 'function') {
            callback = refresh;
            refresh = false;
            filter = null;
        } else if (typeof filter === 'function') {
            callback = filter;
            filter = null;
        }
        this.client.mudlist(refresh, filter)
            .then(result => callback(null, result))
            .catch(callback);
    }

    // Proxy other methods as needed
    isConnected() {
        return this.client.isConnected();
    }

    getStats() {
        return this.client.getClientStats();
    }
}

// Factory functions
function createClient(url, apiKey, mudName, options = {}) {
    return new I3Client(url, apiKey, mudName, options);
}

function createCallbackClient(url, apiKey, mudName, options = {}) {
    return new CallbackI3Client(url, apiKey, mudName, options);
}

// Export for different module systems
if (typeof module !== 'undefined' && module.exports) {
    // CommonJS (Node.js)
    module.exports = {
        I3Client,
        CallbackI3Client,
        I3Config,
        RPCError,
        ConnectionState,
        EventType,
        createClient,
        createCallbackClient
    };
} else if (typeof define === 'function' && define.amd) {
    // AMD (RequireJS)
    define([], function() {
        return {
            I3Client,
            CallbackI3Client,
            I3Config,
            RPCError,
            ConnectionState,
            EventType,
            createClient,
            createCallbackClient
        };
    });
} else {
    // Browser globals
    window.I3Client = I3Client;
    window.CallbackI3Client = CallbackI3Client;
    window.I3Config = I3Config;
    window.RPCError = RPCError;
    window.ConnectionState = ConnectionState;
    window.EventType = EventType;
    window.createI3Client = createClient;
    window.createCallbackI3Client = createCallbackClient;
}