"""Assignment, cost and attachment rules independent of UI and storage."""
from decimal import Decimal, InvalidOperation
from src.domain.priority import Priority
from src.domain.request_status import RequestStatus

MAX_PHOTO_BYTES = 2 * 1024 * 1024

def cost_in_cents(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > Decimal('10000000') or amount != amount.quantize(Decimal('.01')):
            raise ValueError
        return int(amount * 100)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Cost must be between 0 and 10000000, with at most two decimal places.') from None

def validate_photo(data):
    if data is None:
        return None
    if not isinstance(data, bytes) or not data or len(data) > MAX_PHOTO_BYTES:
        raise ValueError('Photo must be a PNG or JPEG of at most 2 MiB.')
    # Parse the actual image; filename and browser MIME are not trusted.
    from io import BytesIO
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in {'PNG', 'JPEG'} or image.width * image.height > 20000000:
                raise ValueError
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ValueError('Photo must be a valid PNG or JPEG, at most 20 million pixels.') from None
    return data

def require_assignment_order(request, requests):
    if request.status is RequestStatus.COMPLETED:
        raise ValueError('Completed requests cannot be assigned.')
    if request.assigned_contractor_key is not None:
        raise ValueError('This request is already assigned.')
    if request.priority is not Priority.CRITICAL and any(
        other.status is RequestStatus.OPEN and other.priority is Priority.CRITICAL
        and other.assigned_contractor_key is None for other in requests
    ):
        raise ValueError('Assign unassigned Critical requests before lower-priority requests.')
