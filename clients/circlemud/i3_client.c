/* ************************************************************************
*  Intermud3 Client Implementation for CircleMUD/tbaMUD                  *
*  Core client functionality and connection management                    *
************************************************************************ */

#include "conf.h"
#include "sysdep.h"
#include "structs.h"
#include "utils.h"
#include "comm.h"
#include "interpreter.h"
#include "handler.h"
#include "db.h"

#include "i3_client.h"

#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <errno.h>
#include <stdarg.h>

/* Global client instance */
i3_client_t *i3_client = NULL;

/* Forward declarations */
static int i3_socket_connect(const char *host, int port);
static int i3_authenticate(void);
static void i3_handle_message(const char *json_str);
static void i3_queue_command(i3_command_t *cmd);
static void i3_queue_event(i3_event_t *event);
static i3_command_t *i3_pop_command(void);
static void i3_free_command(i3_command_t *cmd);
static void i3_heartbeat(void);
static void i3_reconnect(void);

/* Initialize the I3 client */
int i3_initialize(void)
{
    i3_client = (i3_client_t *)calloc(1, sizeof(i3_client_t));
    if (!i3_client) {
        fprintf(stderr, "Failed to allocate I3 client structure\n");
        return -1;
    }
    
    /* Initialize mutexes */
    pthread_mutex_init(&i3_client->command_mutex, NULL);
    pthread_mutex_init(&i3_client->event_mutex, NULL);
    pthread_mutex_init(&i3_client->state_mutex, NULL);
    
    /* Set defaults */
    i3_client->state = I3_STATE_DISCONNECTED;
    i3_client->socket_fd = -1;
    i3_client->authenticated = false;
    i3_client->next_request_id = 1;
    i3_client->max_queue_size = I3_MAX_QUEUE_SIZE;
    i3_client->reconnect_delay = I3_RECONNECT_DELAY;
    
    /* Default configuration */
    i3_client->enable_tell = true;
    i3_client->enable_channels = true;
    i3_client->enable_who = true;
    i3_client->auto_reconnect = true;
    
    /* Load configuration */
    if (i3_load_config("config/i3.conf") < 0) {
        i3_log("Warning: Could not load I3 configuration, using defaults");
    }
    
    /* Create client thread */
    if (pthread_create(&i3_client->thread_id, NULL, i3_client_thread, NULL) != 0) {
        i3_error("Failed to create I3 client thread: %s", strerror(errno));
        free(i3_client);
        i3_client = NULL;
        return -1;
    }
    
    i3_log("I3 client initialized successfully");
    return 0;
}

/* Shutdown the I3 client */
void i3_shutdown(void)
{
    if (!i3_client)
        return;
    
    i3_log("Shutting down I3 client");
    
    /* Signal shutdown */
    pthread_mutex_lock(&i3_client->state_mutex);
    i3_client->state = I3_STATE_SHUTDOWN;
    pthread_mutex_unlock(&i3_client->state_mutex);
    
    /* Wait for thread to finish */
    pthread_join(i3_client->thread_id, NULL);
    
    /* Clean up queues */
    while (i3_client->command_queue_head) {
        i3_command_t *cmd = i3_pop_command();
        i3_free_command(cmd);
    }
    
    while (i3_client->event_queue_head) {
        i3_event_t *event = i3_pop_event();
        i3_free_event(event);
    }
    
    /* Clean up MUD list */
    i3_mud_t *mud = i3_client->mud_list;
    while (mud) {
        i3_mud_t *next = mud->next;
        free(mud);
        mud = next;
    }
    
    /* Destroy mutexes */
    pthread_mutex_destroy(&i3_client->command_mutex);
    pthread_mutex_destroy(&i3_client->event_mutex);
    pthread_mutex_destroy(&i3_client->state_mutex);
    
    /* Free client structure */
    free(i3_client);
    i3_client = NULL;
}

/* Main client thread */
void *i3_client_thread(void *arg)
{
    char buffer[I3_MAX_STRING_LENGTH];
    fd_set read_set;
    struct timeval timeout;
    time_t last_heartbeat = time(NULL);
    
    i3_log("I3 client thread started");
    
    /* Initial connection */
    if (i3_connect() == 0) {
        i3_authenticate();
    }
    
    /* Main loop */
    while (i3_client->state != I3_STATE_SHUTDOWN) {
        /* Check for reconnection */
        if (i3_client->state == I3_STATE_DISCONNECTED && i3_client->auto_reconnect) {
            sleep(i3_client->reconnect_delay);
            i3_reconnect();
            continue;
        }
        
        /* Process outgoing commands */
        i3_command_t *cmd = i3_pop_command();
        if (cmd) {
            json_object *request = i3_create_request(cmd->method, cmd->params);
            i3_send_json(request);
            json_object_put(request);
            i3_free_command(cmd);
        }
        
        /* Check for incoming data */
        if (i3_client->socket_fd >= 0) {
            FD_ZERO(&read_set);
            FD_SET(i3_client->socket_fd, &read_set);
            timeout.tv_sec = 1;
            timeout.tv_usec = 0;
            
            int result = select(i3_client->socket_fd + 1, &read_set, NULL, NULL, &timeout);
            if (result > 0 && FD_ISSET(i3_client->socket_fd, &read_set)) {
                int bytes = recv(i3_client->socket_fd, buffer, sizeof(buffer) - 1, 0);
                if (bytes > 0) {
                    buffer[bytes] = '\0';
                    
                    /* Handle line-delimited JSON */
                    char *line = strtok(buffer, "\n");
                    while (line) {
                        i3_handle_message(line);
                        line = strtok(NULL, "\n");
                    }
                } else if (bytes == 0 || (bytes < 0 && errno != EAGAIN)) {
                    i3_error("Connection lost: %s", strerror(errno));
                    i3_disconnect();
                }
            }
        }
        
        /* Send heartbeat */
        time_t now = time(NULL);
        if (i3_client->state == I3_STATE_CONNECTED && 
            now - last_heartbeat >= I3_HEARTBEAT_INTERVAL) {
            i3_heartbeat();
            last_heartbeat = now;
        }
    }
    
    i3_log("I3 client thread terminating");
    i3_disconnect();
    return NULL;
}

/* Connect to the I3 gateway */
int i3_connect(void)
{
    pthread_mutex_lock(&i3_client->state_mutex);
    i3_client->state = I3_STATE_CONNECTING;
    pthread_mutex_unlock(&i3_client->state_mutex);
    
    i3_log("Connecting to I3 gateway at %s:%d", 
           i3_client->gateway_host, i3_client->gateway_port);
    
    i3_client->socket_fd = i3_socket_connect(i3_client->gateway_host, 
                                             i3_client->gateway_port);
    if (i3_client->socket_fd < 0) {
        i3_error("Failed to connect to I3 gateway");
        pthread_mutex_lock(&i3_client->state_mutex);
        i3_client->state = I3_STATE_DISCONNECTED;
        pthread_mutex_unlock(&i3_client->state_mutex);
        return -1;
    }
    
    i3_client->connect_time = time(NULL);
    i3_log("Connected to I3 gateway");
    return 0;
}

/* Disconnect from the I3 gateway */
void i3_disconnect(void)
{
    if (i3_client->socket_fd >= 0) {
        close(i3_client->socket_fd);
        i3_client->socket_fd = -1;
    }
    
    pthread_mutex_lock(&i3_client->state_mutex);
    if (i3_client->state != I3_STATE_SHUTDOWN) {
        i3_client->state = I3_STATE_DISCONNECTED;
    }
    pthread_mutex_unlock(&i3_client->state_mutex);
    
    i3_client->authenticated = false;
    i3_log("Disconnected from I3 gateway");
}

/* Create TCP socket connection */
static int i3_socket_connect(const char *host, int port)
{
    struct sockaddr_in server_addr;
    struct hostent *server;
    int sock;
    
    /* Create socket */
    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        i3_error("Failed to create socket: %s", strerror(errno));
        return -1;
    }
    
    /* Resolve hostname */
    server = gethostbyname(host);
    if (!server) {
        i3_error("Failed to resolve hostname: %s", host);
        close(sock);
        return -1;
    }
    
    /* Set up server address */
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    memcpy(&server_addr.sin_addr.s_addr, server->h_addr, server->h_length);
    server_addr.sin_port = htons(port);
    
    /* Connect */
    if (connect(sock, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        i3_error("Failed to connect: %s", strerror(errno));
        close(sock);
        return -1;
    }
    
    /* Set non-blocking */
    int flags = fcntl(sock, F_GETFL, 0);
    fcntl(sock, F_SETFL, flags | O_NONBLOCK);
    
    return sock;
}

/* Authenticate with the I3 gateway */
static int i3_authenticate(void)
{
    json_object *params = json_object_new_object();
    json_object_object_add(params, "api_key", json_object_new_string(i3_client->api_key));
    
    json_object *request = i3_create_request("authenticate", params);
    int result = i3_send_json(request);
    json_object_put(request);
    
    if (result < 0) {
        i3_error("Failed to send authentication request");
        return -1;
    }
    
    pthread_mutex_lock(&i3_client->state_mutex);
    i3_client->state = I3_STATE_AUTHENTICATING;
    pthread_mutex_unlock(&i3_client->state_mutex);
    
    i3_log("Authentication request sent");
    return 0;
}

/* Send tell message */
int i3_send_tell(const char *from_user, const char *target_mud, 
                  const char *target_user, const char *message)
{
    if (!i3_client->enable_tell) {
        return -1;
    }
    
    json_object *params = json_object_new_object();
    json_object_object_add(params, "from_user", json_object_new_string(from_user));
    json_object_object_add(params, "target_mud", json_object_new_string(target_mud));
    json_object_object_add(params, "target_user", json_object_new_string(target_user));
    json_object_object_add(params, "message", json_object_new_string(message));
    
    i3_command_t *cmd = (i3_command_t *)calloc(1, sizeof(i3_command_t));
    cmd->id = i3_client->next_request_id++;
    strcpy(cmd->method, "tell");
    cmd->params = params;
    
    i3_queue_command(cmd);
    return 0;
}

/* Send channel message */
int i3_send_channel_message(const char *channel, const char *from_user,
                            const char *message)
{
    if (!i3_client->enable_channels) {
        return -1;
    }
    
    json_object *params = json_object_new_object();
    json_object_object_add(params, "channel", json_object_new_string(channel));
    json_object_object_add(params, "from_user", json_object_new_string(from_user));
    json_object_object_add(params, "message", json_object_new_string(message));
    
    i3_command_t *cmd = (i3_command_t *)calloc(1, sizeof(i3_command_t));
    cmd->id = i3_client->next_request_id++;
    strcpy(cmd->method, "channel_send");
    cmd->params = params;
    
    i3_queue_command(cmd);
    return 0;
}

/* Process events from the queue */
void i3_process_events(void)
{
    i3_event_t *event;
    
    while ((event = i3_pop_event()) != NULL) {
        struct char_data *ch;
        
        switch (event->type) {
        case I3_MSG_TELL:
            /* Find target player */
            ch = get_char_vis(NULL, event->to_user, NULL, FIND_CHAR_WORLD);
            if (ch && !IS_NPC(ch)) {
                send_to_char(ch, "&c[I3 Tell] %s@%s tells you: %s&n\r\n",
                           event->from_user, event->from_mud, event->message);
                /* Store for reply */
                if (GET_LAST_TELL(ch))
                    free(GET_LAST_TELL(ch));
                GET_LAST_TELL(ch) = strdup(event->from_user);
            }
            break;
            
        case I3_MSG_CHANNEL:
            /* Send to all players on channel */
            for (ch = character_list; ch; ch = ch->next) {
                if (!IS_NPC(ch) && PRF_FLAGGED(ch, PRF_I3CHAN)) {
                    send_to_char(ch, "&y[%s] %s@%s: %s&n\r\n",
                               event->channel, event->from_user, 
                               event->from_mud, event->message);
                }
            }
            break;
            
        case I3_MSG_ERROR:
            /* Log errors */
            i3_error("I3 Error: %s", event->message);
            break;
            
        default:
            break;
        }
        
        i3_free_event(event);
    }
}

/* Helper functions */

static void i3_queue_command(i3_command_t *cmd)
{
    pthread_mutex_lock(&i3_client->command_mutex);
    
    if (i3_client->command_queue_size >= i3_client->max_queue_size) {
        pthread_mutex_unlock(&i3_client->command_mutex);
        json_object_put(cmd->params);
        free(cmd);
        return;
    }
    
    cmd->next = NULL;
    if (i3_client->command_queue_tail) {
        i3_client->command_queue_tail->next = cmd;
    } else {
        i3_client->command_queue_head = cmd;
    }
    i3_client->command_queue_tail = cmd;
    i3_client->command_queue_size++;
    
    pthread_mutex_unlock(&i3_client->command_mutex);
}

static i3_command_t *i3_pop_command(void)
{
    pthread_mutex_lock(&i3_client->command_mutex);
    
    i3_command_t *cmd = i3_client->command_queue_head;
    if (cmd) {
        i3_client->command_queue_head = cmd->next;
        if (!i3_client->command_queue_head) {
            i3_client->command_queue_tail = NULL;
        }
        i3_client->command_queue_size--;
    }
    
    pthread_mutex_unlock(&i3_client->command_mutex);
    return cmd;
}

static void i3_free_command(i3_command_t *cmd)
{
    if (cmd->params) {
        json_object_put(cmd->params);
    }
    free(cmd);
}

i3_event_t *i3_pop_event(void)
{
    pthread_mutex_lock(&i3_client->event_mutex);
    
    i3_event_t *event = i3_client->event_queue_head;
    if (event) {
        i3_client->event_queue_head = event->next;
        if (!i3_client->event_queue_head) {
            i3_client->event_queue_tail = NULL;
        }
        i3_client->event_queue_size--;
    }
    
    pthread_mutex_unlock(&i3_client->event_mutex);
    return event;
}

void i3_free_event(i3_event_t *event)
{
    if (event->data) {
        json_object_put(event->data);
    }
    free(event);
}

/* Logging functions */
void i3_log(const char *format, ...)
{
    va_list args;
    char buf[2048];
    time_t now = time(NULL);
    
    va_start(args, format);
    vsnprintf(buf, sizeof(buf), format, args);
    va_end(args);
    
    /* Log to file */
    FILE *fp = fopen("log/i3_client.log", "a");
    if (fp) {
        fprintf(fp, "%s :: %s\n", ctime(&now), buf);
        fclose(fp);
    }
    
    /* Also log to MUD syslog */
    log("I3: %s", buf);
}

void i3_error(const char *format, ...)
{
    va_list args;
    char buf[2048];
    
    va_start(args, format);
    vsnprintf(buf, sizeof(buf), format, args);
    va_end(args);
    
    i3_log("ERROR: %s", buf);
    i3_client->errors++;
}