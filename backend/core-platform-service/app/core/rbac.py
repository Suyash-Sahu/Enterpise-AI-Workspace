from fastapi import Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.models.user import User


def require_role(*allowed_roles: str):
    def checker(current_user: User = Depends(get_current_user)):
        if current_user.role.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )

        return current_user

    return checker