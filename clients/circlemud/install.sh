#!/bin/bash
# Intermud3 Integration Installer for CircleMUD/tbaMUD
# This script helps integrate I3 support into your MUD

echo "==========================================="
echo " Intermud3 Integration Installer"
echo " for CircleMUD/tbaMUD"
echo "==========================================="
echo

# Check if we're in a CircleMUD directory
if [ ! -f "src/comm.c" ] || [ ! -f "src/Makefile" ]; then
    echo "ERROR: This doesn't appear to be a CircleMUD/tbaMUD directory."
    echo "Please run this script from your MUD's root directory."
    exit 1
fi

# Check for JSON-C library
echo "Checking for JSON-C library..."
if ! pkg-config --exists json-c; then
    echo "JSON-C library not found. Installing..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get install -y libjson-c-dev
    elif command -v yum &> /dev/null; then
        sudo yum install -y json-c-devel
    else
        echo "ERROR: Cannot install JSON-C automatically."
        echo "Please install libjson-c-dev manually."
        exit 1
    fi
fi
echo "JSON-C library found."

# Backup existing files
echo
echo "Creating backups..."
if [ -f "src/Makefile" ]; then
    cp src/Makefile src/Makefile.backup
    echo "  Backed up src/Makefile"
fi

# Copy I3 files
echo
echo "Installing I3 integration files..."
cp i3_client.h src/
cp i3_client.c src/
cp i3_commands.c src/
cp i3_protocol.c src/
echo "  Copied source files to src/"

# Create config directory if needed
if [ ! -d "config" ]; then
    mkdir config
fi
cp i3.conf config/i3.conf.example
echo "  Copied configuration template to config/i3.conf.example"

# Apply Makefile patch
echo
echo "Updating Makefile..."
patch -p0 < i3_makefile.patch
if [ $? -eq 0 ]; then
    echo "  Makefile updated successfully"
else
    echo "  WARNING: Makefile patch failed. You may need to update it manually."
fi

# Add command to interpreter
echo
echo "Adding I3 command to interpreter..."
cat >> src/interpreter.c.patch << 'EOF'
--- interpreter.c.orig
+++ interpreter.c
@@ -222,6 +222,7 @@
   { "idea"     , POS_DEAD    , do_gen_write, 0, SCMD_IDEA },
   { "imotd"    , POS_DEAD    , do_gen_ps   , LVL_IMMORT, SCMD_IMOTD },
   { "immlist"  , POS_DEAD    , do_gen_ps   , 0, SCMD_IMMLIST },
+  { "i3"       , POS_DEAD    , do_i3       , 0, 0 },
   { "info"     , POS_SLEEPING, do_gen_ps   , 0, SCMD_INFO },
   { "insult"   , POS_RESTING , do_insult   , 0, 0 },
   { "inventory", POS_DEAD    , do_inventory, 0, 0 },
EOF

if patch -p0 src/interpreter.c < src/interpreter.c.patch 2>/dev/null; then
    echo "  Command added to interpreter"
    rm src/interpreter.c.patch
else
    echo "  Please add the i3 command to interpreter.c manually:"
    echo '    { "i3", POS_DEAD, do_i3, 0, 0 },'
fi

# Add to main.c
echo
echo "Adding I3 initialization to main.c..."
cat >> src/main.c.patch << 'EOF'
--- main.c.orig
+++ main.c
@@ -350,6 +350,10 @@
   boot_db();
   log("Done.");
   
+  log("Initializing Intermud3 client.");
+  i3_initialize();
+  log("Done.");
+  
   log("Entering game loop.");
   
   game_loop(mother_desc);
@@ -359,6 +363,9 @@
   
   log("Closing all sockets.");
   close_all_sockets();
+  
+  log("Shutting down Intermud3 client.");
+  i3_shutdown();
   
   if (circle_reboot) {
EOF

if patch -p0 src/main.c < src/main.c.patch 2>/dev/null; then
    echo "  I3 initialization added to main.c"
    rm src/main.c.patch
else
    echo "  Please add i3_initialize() and i3_shutdown() to main.c manually"
fi

# Add to comm.c game loop
echo
echo "Adding I3 event processing to game loop..."
cat >> src/comm.c.patch << 'EOF'
--- comm.c.orig
+++ comm.c
@@ -890,6 +890,9 @@
     
     /* Process commands we just read from buffer */
     process_commands();
+    
+    /* Process I3 events */
+    i3_process_events();
     
     /* Send queued output out to players */
     process_output();
EOF

if patch -p0 src/comm.c < src/comm.c.patch 2>/dev/null; then
    echo "  I3 event processing added to game loop"
    rm src/comm.c.patch
else
    echo "  Please add i3_process_events() to the game loop in comm.c manually"
fi

# Add includes
echo
echo "Adding required includes..."
for file in main.c comm.c interpreter.c; do
    if ! grep -q "i3_client.h" src/$file; then
        sed -i '/#include "db.h"/a #include "i3_client.h"' src/$file
        echo "  Added include to $file"
    fi
done

# Add to structs.h
echo
echo "Updating structs.h..."
cat >> src/structs.h.patch << 'EOF'
--- structs.h.orig
+++ structs.h
@@ -235,6 +235,7 @@
 #define PRF_DISPAUTO     47  /* Show prompt HP, MP, MV when < 30% */
 #define PRF_BUILDWALK    48  /* Build new rooms while walking */
 #define PRF_AFK          49  /* AFK flag */
+#define PRF_I3CHAN       50  /* Receive I3 channel messages */
 
 /* Player autoexit levels */
 #define EXITS_OFF    0
@@ -760,6 +761,7 @@
    struct char_data *fighting;	  /* Opponent				*/
    struct char_data *hunting;	  /* Char hunted by this char		*/
    struct char_data *group;       /* Group leader (or self if leader) */
+   char *last_tell;               /* Last I3 tell sender for reply    */
 
    struct follow_type *followers; /* List of chars followers		*/
    struct char_data *master;      /* Who is char following?		*/
EOF

if patch -p0 src/structs.h < src/structs.h.patch 2>/dev/null; then
    echo "  structs.h updated"
    rm src/structs.h.patch
else
    echo "  Please update structs.h manually to add PRF_I3CHAN and last_tell"
fi

# Add macro to utils.h
echo
echo "Updating utils.h..."
echo "#define GET_LAST_TELL(ch) ((ch)->last_tell)" >> src/utils.h
echo "  Added GET_LAST_TELL macro"

# Create necessary directories
echo
echo "Creating required directories..."
mkdir -p log
echo "  Created log directory"

# Configuration instructions
echo
echo "==========================================="
echo " Installation Complete!"
echo "==========================================="
echo
echo "Next steps:"
echo
echo "1. Edit config/i3.conf.example and save as config/i3.conf"
echo "   - Set your I3_GATEWAY_HOST and I3_GATEWAY_PORT"
echo "   - Set your I3_API_KEY from the gateway administrator"
echo "   - Configure your MUD name and features"
echo
echo "2. Rebuild your MUD:"
echo "   cd src && make clean && make"
echo
echo "3. Start your MUD and test with:"
echo "   i3 status"
echo "   i3 mudlist"
echo "   i3 tell someone@somemud Hello!"
echo
echo "For troubleshooting, check log/i3_client.log"
echo
echo "Documentation available in README.md"