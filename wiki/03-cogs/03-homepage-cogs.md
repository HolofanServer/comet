# Homepage Cogs

## Overview

Homepage cogs manage integration between the Discord server and the website, handling staff information synchronization and member data management.

## Available Homepage Cogs

### 1. Staff Manager (`staff_manager.py`)

**Purpose**: Synchronizes Discord server roles and member information with the website API.

**Key Features**:
- **Automatic Sync**: Updates staff data every 3 hours via `@tasks.loop(hours=3)`
- **Role-Based Categories**: Organizes members into Staff, Special Thanks, and Testers
- **API Integration**: Sends data to website API endpoint (`https://hfs.jp/api`)
- **Member Data**: Collects avatars, join dates, role colors, and custom messages
- **Caching System**: Local JSON cache with API fallback

#### Staff Role Hierarchy
```python
role_priority = {
    "Administrator": 1,
    "Moderator": 2, 
    "Staff": 3
}
```

#### Member Data Structure
```json
{
  "id": "123456789",
  "name": "DisplayName",
  "role": "Administrator",
  "avatar": "https://cdn.discordapp.com/avatars/...",
  "message": "Custom message",
  "joinedAt": "2024-01-01",
  "joinedAtJp": "2024年01月01日",
  "roleColor": "#ff0000",
  "socials": {}
}
```

#### Categories Managed
1. **Staff Members**: Users with Administrator, Moderator, or Staff roles
2. **Special Thanks**: Users with roles starting with "常連" (regulars)
3. **Testers**: Hardcoded list of specific user IDs with "テスター" role

#### API Integration
- **Endpoint**: `POST /api/members/update`
- **Authentication**: Bearer token via `STAFF_API_KEY`
- **Data Format**: JSON with staff, specialThanks, and testers arrays
- **Fallback**: Local JSON cache if API unavailable

#### Commands Available

| Command | Type | Permission | Description |
|---------|------|------------|-------------|
| `update_staff` | Prefix | Administrator | Manual staff data update |
| `/ひとこと` | Hybrid | Any | Set personal message |
| `/ひとことリセット` | Hybrid | Any | Clear personal message |
| `staff_status` | Prefix | Administrator | View current staff data status |

#### Implementation Details

**Automatic Updates**:
```python
@tasks.loop(hours=3)
async def auto_update_staff(self):
    await self.update_staff_data()
```

**Data Collection Process**:
1. Scan all server members
2. Check for staff roles (Administrator, Moderator, Staff)
3. Check for special thanks roles (starting with "常連")
4. Add hardcoded tester members
5. Collect member data (avatar, join date, role color)
6. Preserve existing messages and social links
7. Send to API and cache locally

**Error Handling**:
- API failures fall back to local cache
- Individual member errors don't stop batch processing
- Comprehensive logging for debugging

**Configuration**:
```python
self.api_endpoint = "https://hfs.jp/api"
self.api_token = settings.staff_api_key
self.config_path = 'config/members.json'
```

---

## Related Documentation

- [API Integration](../04-utilities/02-api-integration.md)
- [Database Management](../04-utilities/01-database-management.md)
- [Configuration Management](../01-architecture/04-configuration-management.md)
- [Error Handling](../02-core/04-error-handling.md)
