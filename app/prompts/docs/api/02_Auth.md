# Authentication

> [← Endpoints](./01_Endpoints.md) | [Knowledge Base →](../knowledge-base/01_Structure.md)

---

## Overview

JWT-based authentication с access и refresh токенами.

---

## Configuration

```env
JWT_SECRET=your-256-bit-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

---

## User Roles

| Role | Permissions |
|------|-------------|
| `admin` | Full access, user management |
| `partner` | All projects, approve major decisions |
| `manager` | Assigned projects, team management |
| `auditor` | Assigned projects only |

---

## Endpoints

### Login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
    "email": "user@example.com",
    "password": "password123"
}
```

Response:
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600
}
```

### Refresh Token

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Logout

```http
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
```

### Get Current User

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

Response:
```json
{
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "role": "auditor",
    "is_active": true
}
```

---

## Token Structure

### Access Token Payload

```json
{
    "sub": "user-uuid",
    "email": "user@example.com",
    "role": "auditor",
    "exp": 1705312800,
    "iat": 1705309200
}
```

### Refresh Token Payload

```json
{
    "sub": "user-uuid",
    "type": "refresh",
    "exp": 1705917600,
    "iat": 1705309200
}
```

---

## Using Tokens

All protected endpoints require Bearer token:

```http
GET /api/v1/projects
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Confirmation Flow

**Critical:** All DB writes require user confirmation via H2 buttons.

When saving data, `confirmed_by` is set from JWT:

```python
@router.post("/actions/save-materiality")
async def save_materiality(
    data: MaterialityData,
    current_user: User = Depends(get_current_user)
):
    # confirmed_by comes from JWT token
    data.confirmed_by = current_user.id
    data.confirmed_at = datetime.utcnow()
    # ... save to DB
```

---

## Middleware

```python
# api/middleware/auth.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(
    token: str = Depends(security)
) -> User:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        user = await get_user_by_id(user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

---

## Security Rules

1. **Never expose JWT_SECRET** — use environment variables
2. **Use HTTPS in production** — tokens can be intercepted
3. **Short access token lifetime** — 60 minutes max
4. **Rotate refresh tokens** — invalidate old on use
5. **Log authentication events** — for audit trail

---

## Related Docs

- [Endpoints](./01_Endpoints.md) — API endpoints
- [Schema](../database/01_Schema.md) — Users table

