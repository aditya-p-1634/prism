import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import verify_password, create_access_token
from app.models.entities import User
from app.schemas.auth import LoginRequestDTO, TokenDTO, UserDTO
from app.schemas.envelope import ResponseEnvelope
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=ResponseEnvelope[TokenDTO])
def login(payload: LoginRequestDTO, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )

    token = create_access_token({"sub": user.id, "role": user.role.value, "email": user.email})
    token_dto = TokenDTO(
        access_token=token,
        token_type="bearer",
        role=user.role,
        full_name=user.full_name
    )

    return ResponseEnvelope[TokenDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        contract_version="1.0",
        data=token_dto
    )

@router.get("/me", response_model=ResponseEnvelope[UserDTO])
def get_me(user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_dto = UserDTO(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active
    )
    return ResponseEnvelope[UserDTO](
        request_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        contract_version="1.0",
        data=user_dto
    )
