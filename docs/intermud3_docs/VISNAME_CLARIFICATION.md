# VISNAME FIELD CLARIFICATION - DEFINITIVE GUIDE

## THE ABSOLUTE TRUTH ABOUT VISNAME

### TELL PACKETS - 8 FIELDS TOTAL
The I3 protocol specification REQUIRES that tell packets have **EXACTLY 8 FIELDS**:

```
Position 0: "tell" (packet type)
Position 1: TTL (integer)
Position 2: originator_mud (string)
Position 3: originator_user (string)
Position 4: target_mud (string)
Position 5: target_user (string - MUST be lowercased)
Position 6: visname (string - REQUIRED, defaults to originator_user)
Position 7: message (string)
```

**TOTAL FIELDS: 8**

### EMOTETO PACKETS - 8 FIELDS TOTAL
The I3 protocol specification REQUIRES that emoteto packets have **EXACTLY 8 FIELDS**:

```
Position 0: "emoteto" (packet type)
Position 1: TTL (integer)
Position 2: originator_mud (string)
Position 3: originator_user (string)
Position 4: target_mud (string)
Position 5: target_user (string - MUST be lowercased)
Position 6: visname (string - REQUIRED, defaults to originator_user)
Position 7: message (string)
```

**TOTAL FIELDS: 8**

## WHAT IS VISNAME?

`visname` is the "visual name" - how the sender wants to be displayed to the recipient. 
- It defaults to the `originator_user` if not specified
- It allows for nicknames or display names different from the actual username
- It is **ALWAYS REQUIRED** in tell and emoteto packets
- It is **ALWAYS** at position 6 in the packet array

## COMMON MISTAKES TO AVOID

1. **WRONG**: Assuming tell packets have 7 fields
   **RIGHT**: Tell packets have 8 fields, visname at position 6

2. **WRONG**: Making visname optional
   **RIGHT**: Visname is REQUIRED, but can default to originator_user

3. **WRONG**: Omitting visname from packet arrays
   **RIGHT**: Always include visname at position 6

## TEST EXPECTATIONS

All tests MUST expect:
- Tell packets to have 8 fields
- Emoteto packets to have 8 fields
- Visname at position 6
- Visname to default to originator_user if not explicitly set

## IMPLEMENTATION CHECKLIST

- [ ] TellPacket.to_lpc_array() returns 8 elements
- [ ] TellPacket.from_lpc_array() expects 8 elements
- [ ] EmotetoPacket.to_lpc_array() returns 8 elements
- [ ] EmotetoPacket.from_lpc_array() expects 8 elements
- [ ] All tell packet tests expect 8 fields
- [ ] All emoteto packet tests expect 8 fields
- [ ] Visname validation sets default to originator_user

## REFERENCES

This is based on the actual I3 protocol as implemented by:
- Dead Souls MUDlib
- LPUniversity reference implementation
- FluffOS I3 daemon
- Nightmare LPMud I3 implementation

**DO NOT DEVIATE FROM THIS SPECIFICATION**