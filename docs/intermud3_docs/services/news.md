# Service: news

Propagate news posts between muds.

## Network Type
Out-of-band (OOB) - Uses direct TCP connections

## Authentication
This service employs the auth service for authentication.

## Connection Protocol
The connection should not disconnect from the server until done dealing with it for the foreseeable future. Messages are exchanged in lockstep with the server.

## Read News Post: news-read-req

```lpc
({
    "news-read-req",
    5,
    originator_mudname,
    originator_username,
    0,
    0,
    newsgroup_name,
    id                     // Post ID
})
```

### Server Response

```lpc
({
    posting_time,          // (int) Unix timestamp
    thread_id,             // (string) Thread identifier
    subject,               // (string) Post subject
    poster,                // (string) Author name
    contents               // (string) Post contents
})
```

## Post News: news-post-req

```lpc
({
    "news-post-req",
    originator_mudname,
    mud_login_port,
    newsgroup,
    thread_id,
    subject,
    poster,
    contents
})
```

Note: This packet does not follow the standard packet form because it is transmitted over the OOB network.

### Server Response
An integer representing the ID of the post, or an error packet.

## List Newsgroups: news-grplist-req

```lpc
({
    "news-grplist-req"
})
```

### Server Response

An array containing an array for each available group:

```lpc
({
    group_name,            // (string) Name of the newsgroup
    first_post_id,         // (int) ID of first post
    last_post_id           // (int) ID of last post
})
```

## Example Usage

1. Client connects to target mud's OOB port
2. Client authenticates using auth service
3. Client sends news request packets
4. Server responds with requested data
5. Connection remains open for multiple operations
6. Client closes connection when done

## Implementation Notes

- This is an OOB service requiring direct TCP connections
- Authentication is required before news operations
- The connection persists for multiple operations
- Errors are returned via the OOB network

## Status
**Note**: This service specification is still under development and may require additional work.