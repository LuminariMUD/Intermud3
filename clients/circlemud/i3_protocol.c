/* ************************************************************************
*  Intermud3 Protocol Implementation for CircleMUD/tbaMUD                *
*  JSON-RPC protocol handling and message parsing                        *
************************************************************************ */

#include "conf.h"
#include "sysdep.h"
#include "structs.h"
#include "utils.h"
#include "comm.h"
#include "i3_client.h"

/* Create a JSON-RPC request */
json_object *i3_create_request(const char *method, json_object *params)
{
    json_object *request = json_object_new_object();
    
    json_object_object_add(request, "jsonrpc", json_object_new_string("2.0"));
    json_object_object_add(request, "id", json_object_new_int(i3_client->next_request_id++));
    json_object_object_add(request, "method", json_object_new_string(method));
    
    if (params) {
        json_object_object_add(request, "params", params);
    }
    
    return request;
}

/* Send JSON object over socket */
int i3_send_json(json_object *obj)
{
    if (!obj || i3_client->socket_fd < 0) {
        return -1;
    }
    
    const char *json_str = json_object_to_json_string_ext(obj, JSON_C_TO_STRING_PLAIN);
    size_t len = strlen(json_str);
    
    /* Add newline for line-delimited protocol */
    char *buffer = (char *)malloc(len + 2);
    strcpy(buffer, json_str);
    strcat(buffer, "\n");
    
    int bytes_sent = send(i3_client->socket_fd, buffer, len + 1, 0);
    free(buffer);
    
    if (bytes_sent > 0) {
        i3_client->messages_sent++;
        i3_debug("Sent: %s", json_str);
    } else {
        i3_error("Failed to send JSON: %s", strerror(errno));
        return -1;
    }
    
    return 0;
}

/* Parse JSON-RPC response or notification */
int i3_parse_response(const char *json_str)
{
    json_object *root = json_tokener_parse(json_str);
    if (!root) {
        i3_error("Failed to parse JSON: %s", json_str);
        return -1;
    }
    
    i3_client->messages_received++;
    i3_debug("Received: %s", json_str);
    
    /* Check if it's a response (has 'id') or notification (no 'id') */
    json_object *id_obj;
    if (json_object_object_get_ex(root, "id", &id_obj)) {
        /* Response to our request */
        i3_handle_response(root);
    } else {
        /* Notification/event from gateway */
        json_object *method_obj;
        if (json_object_object_get_ex(root, "method", &method_obj)) {
            i3_handle_notification(root);
        }
    }
    
    json_object_put(root);
    return 0;
}

/* Handle response to our request */
static void i3_handle_response(json_object *response)
{
    json_object *result_obj, *error_obj;
    
    /* Check for error */
    if (json_object_object_get_ex(response, "error", &error_obj)) {
        json_object *message_obj;
        const char *error_msg = "Unknown error";
        
        if (json_object_object_get_ex(error_obj, "message", &message_obj)) {
            error_msg = json_object_get_string(message_obj);
        }
        
        i3_error("Request failed: %s", error_msg);
        
        /* Queue error event for game thread */
        i3_event_t *event = (i3_event_t *)calloc(1, sizeof(i3_event_t));
        event->type = I3_MSG_ERROR;
        strcpy(event->message, error_msg);
        i3_queue_event(event);
        return;
    }
    
    /* Handle successful result */
    if (json_object_object_get_ex(response, "result", &result_obj)) {
        /* Check what type of response this is */
        json_object *id_obj;
        json_object_object_get_ex(response, "id", &id_obj);
        int request_id = json_object_get_int(id_obj);
        
        /* Handle authentication response */
        json_object *status_obj;
        if (json_object_object_get_ex(result_obj, "status", &status_obj)) {
            const char *status = json_object_get_string(status_obj);
            
            if (strcmp(status, "authenticated") == 0) {
                /* Authentication successful */
                json_object *mud_name_obj, *session_id_obj;
                
                if (json_object_object_get_ex(result_obj, "mud_name", &mud_name_obj)) {
                    strcpy(i3_client->mud_name, json_object_get_string(mud_name_obj));
                }
                
                if (json_object_object_get_ex(result_obj, "session_id", &session_id_obj)) {
                    strcpy(i3_client->session_id, json_object_get_string(session_id_obj));
                }
                
                pthread_mutex_lock(&i3_client->state_mutex);
                i3_client->state = I3_STATE_CONNECTED;
                i3_client->authenticated = true;
                pthread_mutex_unlock(&i3_client->state_mutex);
                
                i3_log("Authenticated as %s with session %s", 
                       i3_client->mud_name, i3_client->session_id);
                
                /* Auto-join default channel if configured */
                if (i3_client->default_channel[0]) {
                    i3_join_channel(i3_client->default_channel, "System");
                }
            }
        }
        
        /* Handle who response */
        json_object *users_obj;
        if (json_object_object_get_ex(result_obj, "users", &users_obj)) {
            i3_handle_who_response(result_obj);
        }
        
        /* Handle mudlist response */
        json_object *muds_obj;
        if (json_object_object_get_ex(result_obj, "muds", &muds_obj)) {
            i3_handle_mudlist_response(result_obj);
        }
        
        /* Handle channel list response */
        json_object *channels_obj;
        if (json_object_object_get_ex(result_obj, "channels", &channels_obj)) {
            i3_handle_channel_list_response(result_obj);
        }
    }
}

/* Handle notification/event from gateway */
static void i3_handle_notification(json_object *notification)
{
    json_object *method_obj, *params_obj;
    
    if (!json_object_object_get_ex(notification, "method", &method_obj)) {
        return;
    }
    
    const char *method = json_object_get_string(method_obj);
    json_object_object_get_ex(notification, "params", &params_obj);
    
    /* Route to appropriate handler */
    if (strcmp(method, "tell_received") == 0) {
        i3_handle_tell_received(params_obj);
    } else if (strcmp(method, "emoteto_received") == 0) {
        i3_handle_emoteto_received(params_obj);
    } else if (strcmp(method, "channel_message") == 0) {
        i3_handle_channel_message(params_obj);
    } else if (strcmp(method, "channel_emote") == 0) {
        i3_handle_channel_emote(params_obj);
    } else if (strcmp(method, "mud_online") == 0) {
        i3_handle_mud_online(params_obj);
    } else if (strcmp(method, "mud_offline") == 0) {
        i3_handle_mud_offline(params_obj);
    } else if (strcmp(method, "channel_joined") == 0) {
        i3_handle_channel_joined(params_obj);
    } else if (strcmp(method, "channel_left") == 0) {
        i3_handle_channel_left(params_obj);
    } else if (strcmp(method, "error_occurred") == 0) {
        i3_handle_error_occurred(params_obj);
    }
}

/* Handle incoming tell */
static void i3_handle_tell_received(json_object *params)
{
    if (!params) return;
    
    i3_event_t *event = (i3_event_t *)calloc(1, sizeof(i3_event_t));
    event->type = I3_MSG_TELL;
    
    json_object *obj;
    if (json_object_object_get_ex(params, "from_mud", &obj)) {
        strcpy(event->from_mud, json_object_get_string(obj));
    }
    if (json_object_object_get_ex(params, "from_user", &obj)) {
        strcpy(event->from_user, json_object_get_string(obj));
    }
    if (json_object_object_get_ex(params, "to_user", &obj)) {
        strcpy(event->to_user, json_object_get_string(obj));
    }
    if (json_object_object_get_ex(params, "message", &obj)) {
        strcpy(event->message, json_object_get_string(obj));
    }
    
    i3_queue_event(event);
}

/* Handle channel message */
static void i3_handle_channel_message(json_object *params)
{
    if (!params) return;
    
    i3_event_t *event = (i3_event_t *)calloc(1, sizeof(i3_event_t));
    event->type = I3_MSG_CHANNEL;
    
    json_object *obj;
    if (json_object_object_get_ex(params, "channel", &obj)) {
        strcpy(event->channel, json_object_get_string(obj));
    }
    if (json_object_object_get_ex(params, "from_mud", &obj)) {
        strcpy(event->from_mud, json_object_get_string(obj));
    }
    if (json_object_object_get_ex(params, "from_user", &obj)) {
        strcpy(event->from_user, json_object_get_string(obj));
    }
    if (json_object_object_get_ex(params, "message", &obj)) {
        strcpy(event->message, json_object_get_string(obj));
    }
    
    i3_queue_event(event);
}

/* Queue event for game thread */
static void i3_queue_event(i3_event_t *event)
{
    pthread_mutex_lock(&i3_client->event_mutex);
    
    if (i3_client->event_queue_size >= i3_client->max_queue_size) {
        pthread_mutex_unlock(&i3_client->event_mutex);
        i3_free_event(event);
        return;
    }
    
    event->next = NULL;
    if (i3_client->event_queue_tail) {
        i3_client->event_queue_tail->next = event;
    } else {
        i3_client->event_queue_head = event;
    }
    i3_client->event_queue_tail = event;
    i3_client->event_queue_size++;
    
    pthread_mutex_unlock(&i3_client->event_mutex);
}

/* Send heartbeat ping */
static void i3_heartbeat(void)
{
    json_object *request = i3_create_request("ping", NULL);
    i3_send_json(request);
    json_object_put(request);
}

/* Attempt reconnection */
static void i3_reconnect(void)
{
    i3_log("Attempting to reconnect...");
    i3_client->reconnects++;
    
    if (i3_connect() == 0) {
        i3_authenticate();
    }
}

/* Load configuration from file */
int i3_load_config(const char *filename)
{
    FILE *fp = fopen(filename, "r");
    if (!fp) {
        return -1;
    }
    
    char line[256];
    char key[128];
    char value[128];
    
    while (fgets(line, sizeof(line), fp)) {
        /* Skip comments and blank lines */
        if (line[0] == '#' || line[0] == '\n') {
            continue;
        }
        
        if (sscanf(line, "%s %s", key, value) != 2) {
            continue;
        }
        
        /* Parse configuration values */
        if (strcasecmp(key, "I3_GATEWAY_HOST") == 0) {
            strcpy(i3_client->gateway_host, value);
        } else if (strcasecmp(key, "I3_GATEWAY_PORT") == 0) {
            i3_client->gateway_port = atoi(value);
        } else if (strcasecmp(key, "I3_API_KEY") == 0) {
            strcpy(i3_client->api_key, value);
        } else if (strcasecmp(key, "I3_MUD_NAME") == 0) {
            strcpy(i3_client->mud_name, value);
        } else if (strcasecmp(key, "I3_ENABLE_TELL") == 0) {
            i3_client->enable_tell = (strcasecmp(value, "YES") == 0);
        } else if (strcasecmp(key, "I3_ENABLE_CHANNELS") == 0) {
            i3_client->enable_channels = (strcasecmp(value, "YES") == 0);
        } else if (strcasecmp(key, "I3_AUTO_RECONNECT") == 0) {
            i3_client->auto_reconnect = (strcasecmp(value, "YES") == 0);
        } else if (strcasecmp(key, "I3_RECONNECT_DELAY") == 0) {
            i3_client->reconnect_delay = atoi(value);
        } else if (strcasecmp(key, "I3_DEFAULT_CHANNEL") == 0) {
            strcpy(i3_client->default_channel, value);
        }
    }
    
    fclose(fp);
    return 0;
}