# Logical Network Layout

## Network Architecture

The logical network of muds is organized into a set of fully connected routers, each acting as a hub for an arbitrary set of muds.

### Router Connectivity
- Routers open and maintain TCP sessions (using MudOS's "MUD" mode) to each other router (fully connected network)
- Each router holds a list of all muds within the intermud and which router each mud is connected to
- A mud has a "preferred" router but records information about all routers for failover
- A mud's preferred router may be changed programmatically to handle load balancing

### Mud-Router Connection
- An active TCP session (in MUD mode) is maintained between a mud and its router
- The mud is responsible for:
  - Opening the connection (see startup-req-2 packet)
  - Maintaining the connection
  - Reconnecting if necessary
  - Shutting down gracefully

### Connection States
- **Graceful exit**: Router propagates "down" state information to other routers and muds
- **Dropped connection**: Router waits 5 minutes before delivering "down" state notification (allows time for reconnection)
- **Removal**: A mud is removed after 7 days of being in the down state

## Network Types

### In-Band Transmissions
The network of TCP sessions between routers and muds is used for "in band" transmissions. Data carried over these connections is limited to "fast response" messages.

### Out-of-Band (OOB) Transmissions
Some services use "out of band" transmissions, separate from the main network:
- Each mud listens at a TCP port for incoming OOB connections
- Connections are opened as needed and closed when transmission completes
- Current OOB services include:
  - Mail
  - News
  - File transfers

### UDP Port
Each mud may maintain a UDP port for specific OOB transmissions. Currently, there are no UDP-based OOB services, so this port is typically not opened.

## MUD Naming

For proper identification within the Intermud network, muds must use a canonical naming system.

### Canonical Names
- The canonical name is the mud's actual name (properly capitalized, with spaces, etc.)
- Examples: "Quendor", "Idea Exchange"
- These names are used in:
  - The mudlist
  - All packet routing
- Case is significant (routers may disallow duplicate names with different casing)

### Router Names
- Routers have assigned names for reference
- Router names are distinguished with a leading asterisk (e.g., "*nightmare")
- Muds may NOT define names with a leading asterisk if they wish to be part of the Intermud

### Name Requirements
- Names must be unique within the network
- Proper capitalization should be maintained
- Spaces are allowed in mud names
- The naming convention ensures proper routing and identification throughout the network