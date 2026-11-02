"""Tenant request use cases; ownership always comes from the current login session."""

from src.domain.maintenance_request import MaintenanceRequest


class TenantMaintenanceService:
    def __init__(self, authentication, current_token, repository):
        self.authentication = authentication
        self.current_token = current_token
        self.repository = repository

    def _tenant(self):
        return self.authentication.get_tenant_account(self.current_token())

    def submit(self, property_unit, title, description, priority):
        tenant = self._tenant()
        request = MaintenanceRequest(property_unit, title, description, priority,
                                     tenant_key=tenant.account_key)
        return self.repository.save(request)

    def list_requests(self):
        tenant = self._tenant()
        return self.repository.list_for_tenant(tenant.account_key)

    def get_request(self, request_id):
        tenant = self._tenant()
        request = self.repository.get_for_tenant(request_id, tenant.account_key)
        if request is None:
            # Another tenant's ID and a missing ID must be indistinguishable.
            raise ValueError("Maintenance request was not found.")
        return request
