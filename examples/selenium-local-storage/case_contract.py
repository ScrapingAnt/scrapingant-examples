"""Expected observations, shared by capture and strict rescan (never by fixture)."""
# case -> expected data region, localStorage value, sessionStorage value, transport
EXTRACTIONS = {
    'empty_startup': ('us', None, None, 'browser'),
    'bootstrap_seed': ('eu', 'eu', None, 'browser'),
    'late_write_without_reload': ('us', 'eu', None, 'browser'),
    'reload_after_late_write': ('eu', 'eu', None, 'browser'),
    'wrong_port': ('us', None, None, 'browser'),
    'query_page_without_storage': ('eu', None, None, 'browser'),
    'session_storage_only': ('us', None, 'eu', 'browser'),
    'delayed_application_update': ('eu', 'eu', None, 'browser'),
    'fresh_driver_empty': ('us', None, None, 'browser'),
    'manual_snapshot_restore': ('eu', 'eu', None, 'browser'),
    'query_parameter_only': ('eu', None, None, 'http'),
    'query_parameter_missing': ('us', None, None, 'http'),
}
DIAGNOSTICS = {
    'opaque_origin', 'argument_roundtrip', 'legacy_interpolation_failure',
    'json_roundtrip', 'crud_selective_removal', 'wrong_origin_restore_rejected',
    'async_precondition', 'snapshot_restore_contents',
}
