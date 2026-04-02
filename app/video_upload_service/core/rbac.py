from fastapi import Depends, HTTPException
from video_upload_service.core.security import verify_jwt_token


def require_admin(user=Depends(verify_jwt_token)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    return user

def require_editor(user=Depends(verify_jwt_token)):
    return user
