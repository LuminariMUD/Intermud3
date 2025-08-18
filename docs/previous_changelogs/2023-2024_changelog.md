# Change Log

## 2024 Updates

### Deathblade - February 15
- Added section for contributors and implementors
- Removed section on reference implementations
- Cleared up a couple OOB items

### Winddle - January 7
- Updated file service, removing local_fname and references to /ftp to remove confusion

## 2023 Updates

### Deathblade - December 20
- Added change log section
- Updated to startup-req-3 for change in locate-reply packet

### Winddle - December 6
- Minor fix to mail service
- Fixed TTL to be int in chan-filter-reply
  
### Winddle - October 20
- Updated mail service specification
- Updated file service specification
- Fixed several broken links in documentation

### Deathblade - October 7
- Updated to startup-req-2
- Modified startup-req-2 packet and mudinfo records to include:
  - admin_email field
  - other_data field
- Added AMCP service
- Stripped really old changelog entries

### Winddle - September 24
- Added typecasting specifications

### Deathblade - September 10
- Added OOB information from Winddle
- Removed auth-user-xxx specifications

### Deathblade - August 9
- Added OOB protocol information

### Deathblade - August 8
- Added auth service
- Added emoteto service
- Added ucache service
- Added section for OOB discussion
- Added more standard error codes
- Renamed news packets to fit within "news name space"
- Added comments to mail, file, and news protocols regarding auth service

## Protocol Versions

### Version 3 (Current)
- Indicated by "-3" suffix in startup-req-3 packet
- Full specification as documented

### Version 2
- Smaller locate-reply packet
- No other changes from Version 3

### Version 1
- Almost identical to current version
- Missing some fields from startup packet
- Missing corresponding fields in info_mapping in mudlist packet

## Notes

- Routers must support all protocol versions
- Routers translate packets between muds with different protocol versions
- Error packets returned for untranslatable services between versions