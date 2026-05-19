"""Domain-level application errors."""


class DuplicateHouseError(Exception):
    """Raised when a house with the same (source, external_id) already exists."""
