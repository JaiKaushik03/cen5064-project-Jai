"""Builder assembles named optional request parts; the product validates itself."""
from src.domain.maintenance_request import MaintenanceRequest

class MaintenanceRequestBuilder:
    def __init__(self, property_unit, title, description, priority):
        self._values = dict(property_unit=property_unit, title=title, description=description, priority=priority)

    def reported_by(self, account):
        profile = account.profile
        self._values.update(tenant_key=account.account_key, tenant_name=profile.full_name,
                            tenant_email=profile.email, tenant_phone=profile.phone_number,
                            tenant_address=profile.address, tenant_unit=profile.unit_number)
        return self

    def at_registered_unit(self, unit_id):
        self._values['registered_unit_id'] = unit_id
        return self

    def with_photo(self, data):
        self._values['photo'] = data
        return self

    def build(self):
        return MaintenanceRequest(**self._values)
