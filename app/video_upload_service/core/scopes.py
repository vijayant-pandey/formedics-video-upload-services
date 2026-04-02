from fastapi import HTTPException

def require_scope(user, scope: str):

    if scope not in user.get("scopes", []):
        raise HTTPException(status_code=403, detail=f"Missing scope: {scope}")
