# PropertyCare creational pattern assessment

The pre-reading asks who creates objects and cautions against forcing a pattern. This map considers the actual final implementation.

| Pattern | Fit in PropertyCare | Reason |
|---|---|---|
| Factory Method | No genuine current fit | Request construction does not vary through creator subclasses. Tenant and owner authorization differ, but both produce the same request type. A helper function alone would not be Factory Method. |
| Abstract Factory | No genuine current fit | There are tenant/owner/contractor stores, but no interchangeable families of matching deployment products. Naming one setup function a factory would not demonstrate the family-selection problem. |
| Builder | Implemented | Requests now combine required issue fields with named optional contact snapshots, unit links and photos. Stepwise assembly avoids a long positional constructor while producing a validated immutable request. |
| Prototype | No genuine current fit | The product has no request-template or clone-use-case. dataclasses.replace supports immutable business transitions, but is not presented as a new template-cloning feature. Copying a tenant request could accidentally carry private identity/history. |
| Singleton | Existing scoped resource reuse, not a new strict Singleton | Streamlit caches authentication composition per normalized account directory and server process so reruns share sessions. Direct AuthenticationService construction remains available for dependency injection and isolated tests. It is not exactly one service across configurations, processes or machines; a global Singleton would weaken test isolation. |

## Builder implementation

`src/domain/request_builder.py` defines `MaintenanceRequestBuilder`. TenantMaintenanceService obtains the account from the current server-issued session, then calls `reported_by(account)`, `with_photo(data)`, `at_registered_unit(id)` and `build()`. Owner submission uses the same Builder without inventing tenant details. The product constructor owns validation; the Builder never saves, authenticates or renders widgets.

```python
request = (MaintenanceRequestBuilder(property_unit, title, description, priority)
           .reported_by(current_account)
           .with_photo(photo)
           .at_registered_unit(unit_id)
           .build())
```

`MaintenanceRequest` is frozen. Reusing a Builder produces separate products; adding a later unit selection cannot mutate a previously built request. Contact values and image bytes are immutable. Invalid required values, incomplete snapshots, malformed images and unsupported values still fail in Domain before storage. Registered-unit existence is checked by Service/Data.

Tests in `test_final_workflow.py` verify independent immutable products, named optional parts, validation and actual service persistence. Screen tests retain existing submission/reset behavior. The shared authentication resource remains injected into use cases; no hidden global session accessor was added.
