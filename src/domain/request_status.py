"""Minimal lifecycle states needed by the priority-change business rule."""

from enum import Enum


class RequestStatus(Enum):
    OPEN = "Open"
    COMPLETED = "Completed"
