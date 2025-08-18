# Service: file

Transfer files between muds.

## Network Type
Out-of-band (OOB) - Uses direct TCP connections

## Authentication
This service employs the auth service. A session token must be obtained from the remote mud before files may be transferred.

## Security
Files are only transferred from/to world-writable directories. Any leading '/' in paths is ignored, and paths are relative to the designated transfer directory.

## List Files: file-list-req / file-list-reply

### Request
```lpc
({
    "file-list-req",
    originator_mudname,
    originator_username,
    dir                    // Directory to list (relative path)
})
```

### Reply
```lpc
({
    "file-list-reply",
    target_username,
    dir_list               // Array of file information
})
```

`dir_list` contains arrays with format:
```lpc
({
    fname,                 // (string) Filename
    fsize,                 // (int) File size in bytes
    ftime                  // (int) Modification time (Unix timestamp)
})
```

## Send File: file-put / file-put-ack

### Put Request
```lpc
({
    "file-put",
    id,                    // (int) Unique transfer ID
    originator_mudname,
    originator_username,
    remote_fname,          // (string) Destination filename
    contents               // (string) File contents
})
```

### Put Acknowledgment
```lpc
({
    "file-put-ack",
    id,                    // (int) Matching transfer ID
    success                // (int) Success status
})
```

## Retrieve File: file-get-req / file-get-reply

### Get Request
```lpc
({
    "file-get-req",
    id,                    // (int) Unique transfer ID
    originator_mudname,
    originator_username,
    remote_fname           // (string) File to retrieve
})
```

### Get Reply
```lpc
({
    "file-get-reply",
    id,                    // (int) Matching transfer ID
    success,               // (int) Success code
    contents               // (string) File contents (if successful)
})
```

## Success Codes

- `-3`: Request failed (write permission)
- `-2`: Request failed (read permission)
- `-1`: Request failed (filepath error)
- `0`: Request failed (unknown error)
- `1`: Request successful

## Limitations

- File size is limited by maximum string length on both sending and receiving muds
- Files are only transferred to/from world-writable directories
- Relative paths only (leading '/' ignored)

## Example Usage

### Listing Files
```lpc
// Request
({ "file-list-req", "OriginMud", "wizard", "public" })

// Reply
({
    "file-list-reply",
    "wizard",
    ({
        ({ "readme.txt", 1024, 1642334400 }),
        ({ "data.csv", 5120, 1642420800 })
    })
})
```

### Transferring a File
```lpc
// Put request
({
    "file-put",
    1001,
    "OriginMud",
    "wizard",
    "public/newfile.txt",
    "This is the file contents..."
})

// Acknowledgment
({ "file-put-ack", 1001, 1 })  // Success
```

## Protocol Flow

1. Obtain auth token via auth service
2. Connect to target's OOB port
3. Authenticate with token
4. Send file operation request
5. Receive response
6. Connection may remain open for additional operations

## Notes

- This service is still in development
- FTP interface may be available as an extended service
- Error responses are returned over the OOB network