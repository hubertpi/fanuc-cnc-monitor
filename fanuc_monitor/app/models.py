import ipaddress
import re
from pydantic import BaseModel, Field, field_validator, ConfigDict


class Endpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(default=8193, ge=1, le=65535)
    timeout: int = Field(default=3, ge=1, le=10)

    @field_validator("host")
    @classmethod
    def address(cls, value):
        try:
            address = ipaddress.ip_address(value)
            if address.is_multicast or address.is_unspecified:
                raise ValueError("Use a specific machine address")
            return value
        except ValueError:
            if re.fullmatch(r"[0-9.]+", value):
                raise ValueError("Invalid IPv4 address")
            labels = value.split(".")
            if not all(re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", s) for s in labels):
                raise ValueError("Use an IP address or DNS hostname, without URL or path")
            return value.lower()


class MachineInput(Endpoint):
    name: str = Field(min_length=1, max_length=80)
    interval: int = Field(default=1, ge=1, le=60)
    enabled: bool = True
    revision: int | None = Field(default=None, ge=1)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value or any(ord(ch) < 32 for ch in value):
            raise ValueError("Enter a printable machine name")
        return value
