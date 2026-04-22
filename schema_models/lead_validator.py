from pydantic import BaseModel , EmailStr , field_validator 
from typing import Literal

class Lead(BaseModel):
    """Validates lead data before storage. Enforces non-empty name/platform and valid email."""
    name : str 
    email : EmailStr 
    platform : str 

    @field_validator("name")
    def validate_name(cls , value):
        """Ensures name is not empty."""
        if len(value.lower().strip()) == 0:
            raise ValueError("The name cannot be empty")

        return value

    @field_validator("platform")
    def validate_platform(cls , value):
        """Ensures platform is not empty."""
        if len(value.lower().strip()) == 0:
            raise ValueError("The platform cannot be empty")

        return value 


class IntentOutput(BaseModel):
    """Structured output for intent classification - GREETING, INQUIRY, or HIGH_INTENT."""
    intent : Literal["GREETING","INQUIRY","HIGH_INTENT"]