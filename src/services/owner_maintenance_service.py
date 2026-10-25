"""Guard the existing shared workspace until tenant/request ownership exists."""

from src.domain.accounts import AccountRole


class OwnerMaintenanceService:
    def __init__(self, authentication, current_token, maintenance):
        self.authentication = authentication
        self.current_token = current_token
        self.maintenance = maintenance

    def _authorize(self):
        self.authentication.require_session(self.current_token(), AccountRole.OWNER)

    def submit(self, *args):
        self._authorize()
        return self.maintenance.submit(*args)

    def list_requests(self):
        self._authorize()
        return self.maintenance.list_requests()

    def change_priority(self, *args):
        self._authorize()
        return self.maintenance.change_priority(*args)
