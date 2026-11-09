"""Registered properties and units validate their own required fields."""
from dataclasses import dataclass
from src.domain.accounts import required_text

@dataclass(frozen=True)
class Property:
    name: str
    address: str
    id: int | None = None

    def __post_init__(self):
        object.__setattr__(self, 'name', required_text(self.name, 'Property name', 100))
        object.__setattr__(self, 'address', required_text(self.address, 'Property address', 300))

@dataclass(frozen=True)
class Unit:
    property_id: int
    number: str
    id: int | None = None

    def __post_init__(self):
        if type(self.property_id) is not int or self.property_id <= 0:
            raise ValueError('Choose a registered property.')
        object.__setattr__(self, 'number', required_text(self.number, 'Unit number', 50))
