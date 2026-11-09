"""Authorized owner and contractor use cases; Domain owns transitions and scheduling."""
from src.domain.accounts import AccountRole, AccessDeniedError, ContractorAccount, validate_signup_password
from src.domain.properties import Property, Unit
from src.domain.request_status import RequestStatus
from src.domain.work_orders import cost_in_cents

class OwnerWorkflowService:
    def __init__(self, authentication, current_token, repository):
        self.authentication, self.current_token, self.repository = authentication, current_token, repository

    def _authorize(self):
        return self.authentication.require_session(self.current_token(), AccountRole.OWNER)

    def list_requests(self):
        self._authorize()
        return self.repository.list_all()

    def list_properties(self):
        self._authorize()
        return self.repository.list_properties()

    def list_units(self):
        self._authorize()
        return self.repository.list_units()

    def register_property(self, name, address):
        self._authorize()
        return self.repository.register_property(Property(name, address))

    def register_unit(self, property_id, number):
        self._authorize()
        return self.repository.register_unit(Unit(property_id, number))

    def list_contractors(self):
        self._authorize()
        return self.authentication.contractors.list_all()

    def register_contractor(self, name, email, password):
        self._authorize()
        validate_signup_password(password, password)
        return self.authentication.contractors.save(ContractorAccount(name, email, self.authentication.passwords.hash(password)))

    def assign(self, request_id, contractor_id, estimated_cost, scheduled_for=None):
        self._authorize()
        contractor = self.authentication.contractors.get_by_id(contractor_id)
        if contractor is None:
            raise ValueError('Contractor was not found.')
        cents = cost_in_cents(estimated_cost)
        if scheduled_for is not None:
            scheduled_for = str(scheduled_for)
        return self.repository.transact_update(request_id, lambda request, requests:
            request.assign(contractor.account_key, contractor.full_name, cents, requests, scheduled_for))

    def complete(self, request_id, confirmed, actual_cost='0', notes=''):
        self._authorize()
        cents = cost_in_cents(actual_cost)
        return self.repository.transact_update(request_id, lambda request, requests:
            request.complete(confirmed=confirmed, actual_cost=cents, notes=notes))

class ContractorWorkflowService:
    def __init__(self, authentication, current_token, repository):
        self.authentication, self.current_token, self.repository = authentication, current_token, repository

    def _principal(self):
        return self.authentication.require_session(self.current_token(), AccountRole.CONTRACTOR)

    def list_requests(self):
        principal = self._principal()
        return self.repository.list_for_contractor(principal.account_key)

    def start_work(self, request_id):
        principal = self._principal()
        def transition(request, requests):
            if request.assigned_contractor_key != principal.account_key:
                raise AccessDeniedError('Assigned work was not found.')
            return request.start_work()
        return self.repository.transact_update(request_id, transition)

    def complete(self, request_id, confirmed, actual_cost='0', notes=''):
        principal = self._principal()
        cents = cost_in_cents(actual_cost)
        def transition(request, requests):
            if request.assigned_contractor_key != principal.account_key:
                raise AccessDeniedError('Assigned work was not found.')
            return request.complete(confirmed=confirmed, actual_cost=cents, notes=notes)
        return self.repository.transact_update(request_id, transition)
