"""Authorize access to the owner's shared maintenance workspace."""

from src.domain.accounts import AccountRole


class OwnerMaintenanceService:
    def __init__(self, authentication, current_token, maintenance):
        self.authentication = authentication
        self.current_token = current_token
        self.maintenance = maintenance

    def _authorize(self):
        self.authentication.require_session(self.current_token(), AccountRole.OWNER)

    def submit(self, *args, **kwargs):
        self._authorize()
        return self.maintenance.submit(*args, **kwargs)

    def list_requests(self):
        self._authorize()
        return self.maintenance.list_requests()

    def change_priority(self, *args, **kwargs):
        self._authorize()
        return self.maintenance.change_priority(*args, **kwargs)

    def list_units(self):
        self._authorize()
        return self.maintenance.list_units()

    def list_requests_page(self, **filters):
        self._authorize()
        return self.maintenance.list_requests_page(**filters)

    def get_request(self, request_id):
        self._authorize()
        return self.maintenance.get_request(request_id)
