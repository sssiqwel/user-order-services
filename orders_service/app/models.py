from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    email: str


class OrderIn(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "user_id": 1,
                    "item": "Настольная лампа",
                    "quantity": 2,
                }
            ]
        },
    )

    user_id: int = Field(ge=1, description="Идентификатор пользователя из Users API")
    item: str = Field(min_length=1, max_length=200, description="Название товара")
    quantity: int = Field(ge=1, le=1000, description="Количество")

    @field_validator("item")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(description="Идентификатор, назначается сервером")
    user_id: int
    item: str
    quantity: int
    user: UserSnapshot = Field(description="Актуальные данные пользователя из Users API")


class ErrorResponse(BaseModel):
    detail: str
