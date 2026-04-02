from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from video_upload_service.core.config import settings

security = HTTPBearer()

# auth provider interface and implementations
class AuthProvider:

    def validate(self, token: str) -> dict:
        raise NotImplementedError

# DEV AUTH PROVIDER (CURRENT BEHAVIOUR)
class DevAuthProvider(AuthProvider):

    def validate(self, token: str) -> dict:

        if token not in ["dev-admin-token", "dev-editor-token"]:
            raise HTTPException(status_code=401, detail="Invalid token")

        if token == "dev-admin-token":
            role = "admin"
            scopes = [
                "upload:create",
                "upload:retry",
                "upload:read"
            ]
        else:
            role = "editor"
            scopes = ["upload:read"]

        return {
            "user_id": "dev_user",
            "role": role,
            "scopes": scopes
        }


# select provier based on env
def get_auth_provider() -> AuthProvider:

    # Later you will switch here to JWT provider
    if settings.ENV == "dev":
        return DevAuthProvider()

    # Placeholder for production provider
    return DevAuthProvider()


# main dependency to verify JWT and extract user info
def verify_jwt_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials

    provider = get_auth_provider()

    return provider.validate(token)



# JWT Auth Provider (Production placeholder, noreal JWT)
class JwtAuthProvider(AuthProvider):
    def validate(self, token: str) -> dict:
        #  In future we decode the jwt, verify the signature and extract the scopes and roles
        # FOr now i just blockthe usage so devs know JWT is not wired
        raise HTTPException(
            status_code=501,
            detail="JWT Auth not confirmet Yet"
        )