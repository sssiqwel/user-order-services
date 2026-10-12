from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserIn(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "Анна Иванова",
                    "email": "anna@example.com",
                }
            ]
        },
    )

    name: str = Field(min_length=1, max_length=100, description="Имя пользователя")
    email: str = Field(
        min_length=3,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        description="Уникальный email",
    )

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class User(UserIn):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(description="Идентификатор, назначается сервером")


class ErrorResponse(BaseModel):
    detail: str
