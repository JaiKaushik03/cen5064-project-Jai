"""Owner tables, registration forms and explicit completion confirmation."""
import streamlit as st
from src.domain.request_status import RequestStatus
from src.presentation.ui import clear_feedback, history_page, show_photos

def action(service, method, keys, success, *, secret_key=None):
    clear_feedback()
    try:
        getattr(service, method)(*(st.session_state[key] for key in keys))
    except ValueError as error:
        st.session_state['workflow_error'] = str(error)
    else:
        st.session_state['workflow_success'] = success
    finally:
        if secret_key:
            st.session_state[secret_key] = ''

def issue_rows(requests):
    return [{
        'ID': r.id, 'Issue title': r.title, 'Description': r.description,
        'Property / Unit': r.property_unit, 'Priority': r.priority.value,
        'Status': 'Fixed' if r.status is RequestStatus.COMPLETED else r.status.value,
        'Submitted (UTC)': r.created_at, 'Fixed (UTC)': r.completed_at or '',
        'Tenant': r.tenant_name or 'Unavailable (legacy/unassigned)',
        'Email': r.tenant_email or '', 'Phone': r.tenant_phone or '',
        'Tenant address': r.tenant_address or '', 'Tenant unit': r.tenant_unit or '',
        'Contractor': r.assigned_contractor_name or '',
        'Assigned (UTC)': r.assigned_at or '',
        'Scheduled date': r.scheduled_for or '',
        'Work progress': 'Fixed' if r.status is RequestStatus.COMPLETED else ('In Progress' if r.work_started_at else ('Assigned' if r.assigned_contractor_key else 'Unassigned')),
        'Estimated cost ($)': '' if r.estimated_cost_cents is None else f'{r.estimated_cost_cents / 100:.2f}',
        'Actual cost ($)': '' if r.actual_cost_cents is None else f'{r.actual_cost_cents / 100:.2f}',
        'Completion notes': r.completion_notes,
    } for r in requests]

def start_action(service, request_id):
    clear_feedback()
    try:
        service.start_work(request_id)
    except ValueError as error:
        st.session_state['workflow_error'] = str(error)
    else:
        st.session_state.pop('workflow_error', None)
        st.session_state['workflow_success'] = f'Work started on request #{request_id}.'

def open_completion(request_id):
    clear_feedback()
    st.session_state['pending_completion'] = request_id
    st.session_state[f'confirm_fix_{request_id}'] = False

@st.dialog('Confirm Mark Fixed')
def completion_dialog(service, request_id):
    st.write(f'Mark request #{request_id} Fixed? It will remain in the maintenance history.')
    st.caption('Confirm only after the repair is finished. Cancel closes this window without changing the request.')
    with st.form(f'complete_{request_id}'):
        st.checkbox('I confirm this issue has been fixed *', key=f'confirm_fix_{request_id}')
        st.text_input('Actual repair cost ($) *', value='0.00', key=f'actual_cost_{request_id}')
        st.text_area('Completion notes (optional)', max_chars=4000, key=f'completion_notes_{request_id}')
        submitted = st.form_submit_button('Submit')
    if submitted:
        try:
            service.complete(request_id, st.session_state[f'confirm_fix_{request_id}'],
                             st.session_state[f'actual_cost_{request_id}'], st.session_state[f'completion_notes_{request_id}'])
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state.pop('pending_completion', None)
            st.session_state['workflow_success'] = f'Request #{request_id} marked Fixed.'
            st.rerun()
    if st.button('Cancel'):
        st.session_state.pop('pending_completion', None)
        st.rerun()

def render_issues(service, *, contractor=False):
    if st.session_state.get('workflow_success'):
        st.success(st.session_state['workflow_success'])
    if st.session_state.get('workflow_error'):
        st.error(st.session_state['workflow_error'])
    totals = service.totals()
    estimated_card, actual_card = st.columns(2)
    estimated_card.metric("Estimated repair costs", f"${totals['estimated'] / 100:,.2f}")
    actual_card.metric("Recorded actual costs", f"${totals['actual'] / 100:,.2f}")
    st.subheader('Assigned Active Issues' if contractor else 'Active Issues')
    active = history_page(service, "active", status=RequestStatus.OPEN)
    if active:
        st.dataframe(issue_rows(active), hide_index=True)
        for request in active:
            if contractor and request.work_started_at is None:
                st.button(f'Start work #{request.id}', key=f'start_{request.id}',
                          on_click=start_action, args=(service, request.id))
            st.button(f'Mark Fixed #{request.id}', key=f'mark_fixed_{request.id}',
                      on_click=open_completion, args=(request.id,))
    else:
        st.info('No active issues. New requests will appear here.' if not contractor else 'No active issues. Your assigned repairs will appear here when an owner assigns work to you.')
    st.subheader('Fixed Issues')
    fixed = history_page(service, "fixed", status=RequestStatus.COMPLETED)
    if fixed:
        st.dataframe(issue_rows(fixed), hide_index=True)
    else:
        st.info('No fixed issues yet.')
    st.caption(f"Total estimated repair cost: ${totals['estimated'] / 100:.2f}. Recorded actual cost: ${totals['actual'] / 100:.2f}.")
    show_photos(service, [*active, *fixed])
    pending = st.session_state.get('pending_completion')
    if pending is not None:
        completion_dialog(service, pending)

def render_catalog(service):
    st.subheader('Properties and units')
    st.caption('Register buildings and units to organize repair history. Tenants may also report an unregistered location.')
    properties = service.list_properties()
    with st.form('register_property'):
        st.text_input('Property name *', key='property_name', max_chars=100)
        st.text_input('Property address *', key='property_address', max_chars=300)
        st.form_submit_button('Register property', on_click=action,
                              args=(service, 'register_property', ('property_name', 'property_address'), 'Property registered.'))
    if properties:
        st.dataframe(properties, hide_index=True)
        names = {p['id']: p['name'] for p in properties}
        with st.form('register_unit'):
            st.selectbox('Property *', list(names), format_func=names.get, key='unit_property_id')
            st.text_input('Unit number *', key='new_unit_number', max_chars=50)
            st.form_submit_button('Register unit', on_click=action,
                                  args=(service, 'register_unit', ('unit_property_id', 'new_unit_number'), 'Unit registered.'))
    units = service.list_units()
    if units:
        st.dataframe(units, hide_index=True)
        st.subheader('Maintenance history by registered unit')
        selected = st.selectbox('History unit', [u['id'] for u in units],
            format_func=lambda value: next(f"{u['name']} / {u['number']}" for u in units if u['id'] == value))
        history = history_page(service, "unit_history", unit_id=selected)
        if history:
            st.dataframe(issue_rows(history), hide_index=True)
            totals = service.totals(unit_id=selected)
            st.caption(f"Unit estimated cost: ${totals['estimated'] / 100:.2f}; actual cost: ${totals['actual'] / 100:.2f}.")
        else:
            st.info('No maintenance history for this registered unit.')

def render_assignments(service):
    st.subheader('Contractors and work assignments')
    st.caption('Contractor accounts are created by an owner; there is no public contractor signup.')
    with st.form('register_contractor'):
        st.text_input('Contractor name *', key='new_contractor_name', max_chars=100)
        st.text_input('Contractor email *', key='new_contractor_email')
        st.text_input('Initial contractor password *', type='password', key='new_contractor_password')
        st.form_submit_button('Create contractor account', on_click=action,
            args=(service, 'register_contractor', ('new_contractor_name', 'new_contractor_email', 'new_contractor_password'), 'Contractor account created.'),
            kwargs={'secret_key': 'new_contractor_password'})
    contractors = service.list_contractors()
    if contractors:
        st.dataframe([{'ID': c.id, 'Name': c.full_name, 'Email': c.email} for c in contractors], hide_index=True)
    requests = history_page(service, "assignments", status=RequestStatus.OPEN, unassigned=True)
    if contractors and requests:
        by_id = {r.id: r for r in requests}
        people = {c.id: c.full_name for c in contractors}
        st.caption('Assign unassigned Critical requests first. Completed requests cannot be assigned or reprioritized.')
        with st.form('assign_work'):
            st.selectbox('Unassigned request *', list(by_id), format_func=lambda value: f'#{value}: {by_id[value].title} ({by_id[value].priority.value})', key='assign_request_id')
            st.selectbox('Contractor *', list(people), format_func=people.get, key='assign_contractor_id')
            st.text_input('Estimated repair cost ($) *', value='0.00', key='estimated_cost')
            st.date_input('Scheduled date', value=None, key='scheduled_date', help='Optional. Leave empty if a repair date has not been agreed.')
            st.form_submit_button('Assign work', on_click=action,
                args=(service, 'assign', ('assign_request_id', 'assign_contractor_id', 'estimated_cost', 'scheduled_date'), 'Work assigned.'))
