import json
from .models import Decision, Permission, Proposal, Record


def same(a, b):
    # JSON types matter: false must not authorize 0, nor 1 authorize true.
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)


def decide(permission: Permission | None, proposal: Proposal, record: Record | None) -> Decision:
    def result(verdict, code, reason):
        return Decision(verdict=verdict, code=code, reason=reason)
    if permission is None:
        return result("pause", "permission_missing", "A locked permission is required before saving.")
    if (proposal.resource_type, proposal.record_id) != (permission.resource_type, permission.record_id):
        return result("reject", "wrong_record", "This permission belongs to a different record. Nothing was saved.")
    if proposal.operation in permission.forbidden_operations or proposal.operation != "update":
        return result("reject", "forbidden_operation", "This operation is outside the permission.")
    if record is None:
        return result("reject", "record_missing", "The authorized record no longer exists.")
    if (record.resource_type, record.record_id) != (permission.resource_type, permission.record_id):
        return result("reject", "wrong_record", "The stored record does not match the permission.")
    if record.version != permission.version or proposal.version != permission.version:
        return result("reject", "stale_version", "The record changed. A new permission is required.")
    if not permission.set_fields or set(permission.set_fields) & set(permission.preserve_fields):
        return result("pause", "invalid_permission", "The permission has incomplete or conflicting rules.")
    if any(k not in record.fields or not same(record.fields[k], v) for k, v in permission.preserve_fields.items()):
        return result("reject", "preserved_field", "A protected field no longer matches the permission.")
    if any(k not in record.fields for k in proposal.fields | permission.set_fields):
        return result("reject", "unknown_field", "The write contains an unknown field.")
    expected = record.fields | permission.set_fields
    if not same(record.fields | proposal.fields, expected):
        return result("reject", "field_mismatch", "The proposed values are not exactly the authorized change.")
    return result("allow", "exact_write", "Exact authorized change. Saved and read back.")
