/* ************************************************************************
*  Intermud3 Command Implementations for CircleMUD/tbaMUD                *
*  Player and immortal command handlers                                  *
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

/* Command prototypes */
ACMD(do_i3);
ACMD(do_i3tell);
ACMD(do_i3reply);
ACMD(do_i3who);
ACMD(do_i3finger);
ACMD(do_i3locate);
ACMD(do_i3mudlist);
ACMD(do_i3channel);
ACMD(do_i3chat);

/* Main I3 command dispatcher */
ACMD(do_i3)
{
    char arg1[MAX_INPUT_LENGTH];
    char arg2[MAX_INPUT_LENGTH];
    
    if (!i3_client || !i3_is_connected()) {
        send_to_char(ch, "The Intermud3 network is currently unavailable.\r\n");
        return;
    }
    
    two_arguments(argument, arg1, arg2);
    
    if (!*arg1) {
        send_to_char(ch, "Intermud3 Commands:\r\n");
        send_to_char(ch, "  i3 tell <user>@<mud> <message>  - Send a tell\r\n");
        send_to_char(ch, "  i3 reply <message>               - Reply to last tell\r\n");
        send_to_char(ch, "  i3 who <mud>                     - List users on a MUD\r\n");
        send_to_char(ch, "  i3 finger <user>@<mud>           - Get user info\r\n");
        send_to_char(ch, "  i3 locate <user>                 - Find user on network\r\n");
        send_to_char(ch, "  i3 mudlist                       - List all MUDs\r\n");
        send_to_char(ch, "  i3 channel <cmd> [args]          - Channel commands\r\n");
        send_to_char(ch, "  i3 chat <message>                - Chat on default channel\r\n");
        
        if (GET_LEVEL(ch) >= LVL_IMMORT) {
            send_to_char(ch, "\r\nImmortal Commands:\r\n");
            send_to_char(ch, "  i3 status                        - Show connection status\r\n");
            send_to_char(ch, "  i3 stats                         - Show statistics\r\n");
            send_to_char(ch, "  i3 reconnect                     - Force reconnection\r\n");
            send_to_char(ch, "  i3 config                        - Show configuration\r\n");
        }
        return;
    }
    
    /* Route to appropriate subcommand */
    if (!strcasecmp(arg1, "tell")) {
        do_i3tell(ch, argument + 5, cmd, subcmd);
    } else if (!strcasecmp(arg1, "reply")) {
        do_i3reply(ch, argument + 6, cmd, subcmd);
    } else if (!strcasecmp(arg1, "who")) {
        do_i3who(ch, arg2, cmd, subcmd);
    } else if (!strcasecmp(arg1, "finger")) {
        do_i3finger(ch, argument + 7, cmd, subcmd);
    } else if (!strcasecmp(arg1, "locate")) {
        do_i3locate(ch, arg2, cmd, subcmd);
    } else if (!strcasecmp(arg1, "mudlist")) {
        do_i3mudlist(ch, "", cmd, subcmd);
    } else if (!strcasecmp(arg1, "channel")) {
        do_i3channel(ch, argument + 8, cmd, subcmd);
    } else if (!strcasecmp(arg1, "chat")) {
        do_i3chat(ch, argument + 5, cmd, subcmd);
    } else if (!strcasecmp(arg1, "status") && GET_LEVEL(ch) >= LVL_IMMORT) {
        char buf[MAX_STRING_LENGTH];
        snprintf(buf, sizeof(buf), 
                "I3 Status: %s\r\n"
                "MUD Name: %s\r\n"
                "Session: %s\r\n"
                "Uptime: %ld seconds\r\n",
                i3_get_state_string(),
                i3_client->mud_name,
                i3_client->session_id,
                time(NULL) - i3_client->connect_time);
        send_to_char(ch, buf);
    } else if (!strcasecmp(arg1, "stats") && GET_LEVEL(ch) >= LVL_IMMORT) {
        char buf[MAX_STRING_LENGTH];
        i3_get_statistics(buf, sizeof(buf));
        send_to_char(ch, buf);
    } else if (!strcasecmp(arg1, "reconnect") && GET_LEVEL(ch) >= LVL_GOD) {
        i3_disconnect();
        i3_connect();
        send_to_char(ch, "Reconnecting to I3 gateway...\r\n");
    } else {
        send_to_char(ch, "Unknown I3 command. Type 'i3' for help.\r\n");
    }
}

/* I3 Tell command */
ACMD(do_i3tell)
{
    char target[MAX_INPUT_LENGTH];
    char *message;
    char target_user[128], target_mud[128];
    
    if (!i3_client || !i3_is_connected()) {
        send_to_char(ch, "The Intermud3 network is currently unavailable.\r\n");
        return;
    }
    
    /* Parse arguments */
    message = one_argument(argument, target);
    skip_spaces(&message);
    
    if (!*target || !*message) {
        send_to_char(ch, "Usage: i3 tell <user>@<mud> <message>\r\n");
        return;
    }
    
    /* Parse user@mud format */
    char *at_sign = strchr(target, '@');
    if (!at_sign) {
        send_to_char(ch, "You must specify both user and MUD: <user>@<mud>\r\n");
        return;
    }
    
    *at_sign = '\0';
    strcpy(target_user, target);
    strcpy(target_mud, at_sign + 1);
    
    /* Validate MUD exists */
    i3_mud_t *mud = i3_find_mud(target_mud);
    if (!mud) {
        send_to_char(ch, "Unknown MUD: %s\r\n", target_mud);
        return;
    }
    
    if (!mud->online) {
        send_to_char(ch, "That MUD is currently offline.\r\n");
        return;
    }
    
    /* Send the tell */
    if (i3_send_tell(GET_NAME(ch), target_mud, target_user, message) == 0) {
        send_to_char(ch, "You tell %s@%s: %s\r\n", target_user, target_mud, message);
        
        /* Store for reply */
        if (GET_LAST_TELL(ch))
            free(GET_LAST_TELL(ch));
        char reply_target[256];
        snprintf(reply_target, sizeof(reply_target), "%s@%s", target_user, target_mud);
        GET_LAST_TELL(ch) = strdup(reply_target);
    } else {
        send_to_char(ch, "Failed to send tell.\r\n");
    }
}

/* I3 Reply command */
ACMD(do_i3reply)
{
    char target_user[128], target_mud[128];
    
    if (!i3_client || !i3_is_connected()) {
        send_to_char(ch, "The Intermud3 network is currently unavailable.\r\n");
        return;
    }
    
    skip_spaces(&argument);
    
    if (!*argument) {
        send_to_char(ch, "Reply with what?\r\n");
        return;
    }
    
    if (!GET_LAST_TELL(ch)) {
        send_to_char(ch, "You have no one to reply to.\r\n");
        return;
    }
    
    /* Parse stored reply target */
    char *at_sign = strchr(GET_LAST_TELL(ch), '@');
    if (!at_sign) {
        send_to_char(ch, "Invalid reply target.\r\n");
        return;
    }
    
    strncpy(target_user, GET_LAST_TELL(ch), at_sign - GET_LAST_TELL(ch));
    target_user[at_sign - GET_LAST_TELL(ch)] = '\0';
    strcpy(target_mud, at_sign + 1);
    
    /* Send the reply */
    if (i3_send_tell(GET_NAME(ch), target_mud, target_user, argument) == 0) {
        send_to_char(ch, "You reply to %s@%s: %s\r\n", target_user, target_mud, argument);
    } else {
        send_to_char(ch, "Failed to send reply.\r\n");
    }
}

/* I3 Who command */
ACMD(do_i3who)
{
    if (!i3_client || !i3_is_connected()) {
        send_to_char(ch, "The Intermud3 network is currently unavailable.\r\n");
        return;
    }
    
    skip_spaces(&argument);
    
    if (!*argument) {
        send_to_char(ch, "Usage: i3 who <mud>\r\n");
        return;
    }
    
    /* Validate MUD exists */
    i3_mud_t *mud = i3_find_mud(argument);
    if (!mud) {
        send_to_char(ch, "Unknown MUD: %s\r\n", argument);
        return;
    }
    
    if (!mud->online) {
        send_to_char(ch, "That MUD is currently offline.\r\n");
        return;
    }
    
    /* Request who list */
    if (i3_request_who(argument) == 0) {
        send_to_char(ch, "Requesting who list from %s...\r\n", argument);
    } else {
        send_to_char(ch, "Failed to request who list.\r\n");
    }
}

/* I3 Channel command */
ACMD(do_i3channel)
{
    char arg1[MAX_INPUT_LENGTH];
    char arg2[MAX_INPUT_LENGTH];
    
    if (!i3_client || !i3_is_connected()) {
        send_to_char(ch, "The Intermud3 network is currently unavailable.\r\n");
        return;
    }
    
    two_arguments(argument, arg1, arg2);
    
    if (!*arg1) {
        send_to_char(ch, "Channel commands:\r\n");
        send_to_char(ch, "  i3 channel list              - List available channels\r\n");
        send_to_char(ch, "  i3 channel join <channel>    - Join a channel\r\n");
        send_to_char(ch, "  i3 channel leave <channel>   - Leave a channel\r\n");
        send_to_char(ch, "  i3 channel who <channel>     - List channel members\r\n");
        return;
    }
    
    if (!strcasecmp(arg1, "list")) {
        if (i3_list_channels() == 0) {
            send_to_char(ch, "Requesting channel list...\r\n");
        }
    } else if (!strcasecmp(arg1, "join")) {
        if (!*arg2) {
            send_to_char(ch, "Join which channel?\r\n");
            return;
        }
        if (i3_join_channel(arg2, GET_NAME(ch)) == 0) {
            send_to_char(ch, "Joining channel '%s'...\r\n", arg2);
            SET_BIT_AR(PRF_FLAGS(ch), PRF_I3CHAN);
        }
    } else if (!strcasecmp(arg1, "leave")) {
        if (!*arg2) {
            send_to_char(ch, "Leave which channel?\r\n");
            return;
        }
        if (i3_leave_channel(arg2, GET_NAME(ch)) == 0) {
            send_to_char(ch, "Leaving channel '%s'...\r\n", arg2);
        }
    } else {
        send_to_char(ch, "Unknown channel command.\r\n");
    }
}

/* I3 Chat command - send to default channel */
ACMD(do_i3chat)
{
    if (!i3_client || !i3_is_connected()) {
        send_to_char(ch, "The Intermud3 network is currently unavailable.\r\n");
        return;
    }
    
    if (!PRF_FLAGGED(ch, PRF_I3CHAN)) {
        send_to_char(ch, "You must join a channel first.\r\n");
        return;
    }
    
    skip_spaces(&argument);
    
    if (!*argument) {
        send_to_char(ch, "Chat what?\r\n");
        return;
    }
    
    const char *channel = i3_client->default_channel[0] ? 
                         i3_client->default_channel : "intermud";
    
    if (i3_send_channel_message(channel, GET_NAME(ch), argument) == 0) {
        send_to_char(ch, "&y[%s] You: %s&n\r\n", channel, argument);
    } else {
        send_to_char(ch, "Failed to send message.\r\n");
    }
}

/* Helper function implementations */

const char *i3_get_state_string(void)
{
    switch (i3_client->state) {
    case I3_STATE_DISCONNECTED:
        return "Disconnected";
    case I3_STATE_CONNECTING:
        return "Connecting";
    case I3_STATE_AUTHENTICATING:
        return "Authenticating";
    case I3_STATE_CONNECTED:
        return "Connected";
    case I3_STATE_RECONNECTING:
        return "Reconnecting";
    default:
        return "Unknown";
    }
}

void i3_get_statistics(char *buf, size_t bufsize)
{
    snprintf(buf, bufsize,
            "I3 Statistics:\r\n"
            "  Messages Sent: %lu\r\n"
            "  Messages Received: %lu\r\n"
            "  Errors: %lu\r\n"
            "  Reconnects: %lu\r\n"
            "  Command Queue: %d/%d\r\n"
            "  Event Queue: %d/%d\r\n"
            "  Channels: %d\r\n"
            "  MUDs Known: %d\r\n",
            i3_client->messages_sent,
            i3_client->messages_received,
            i3_client->errors,
            i3_client->reconnects,
            i3_client->command_queue_size,
            i3_client->max_queue_size,
            i3_client->event_queue_size,
            i3_client->max_queue_size,
            i3_client->channel_count,
            0); /* TODO: Count MUDs */
}

i3_mud_t *i3_find_mud(const char *name)
{
    i3_mud_t *mud;
    
    for (mud = i3_client->mud_list; mud; mud = mud->next) {
        if (!strcasecmp(mud->name, name)) {
            return mud;
        }
    }
    return NULL;
}

bool i3_is_connected(void)
{
    return i3_client && i3_client->state == I3_STATE_CONNECTED;
}