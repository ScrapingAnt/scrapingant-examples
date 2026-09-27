"""Predeclared case hypotheses, separate from browser execution."""
# (response region, current storage value, query value, observed origin label)
EXTRACTION = {
    'early_missing_only_seed': ('eu', 'eu', 'eu', 'primary'),
    'late_write_without_reload': ('us', 'eu', 'us', 'primary'),
    'late_write_then_reload': ('eu', 'eu', 'eu', 'primary'),
    'fresh_isolated_context': ('us', None, 'us', 'primary'),
    'storage_state_restore': ('eu', 'eu', 'eu', 'primary'),
    'same_context_new_page': ('eu', 'eu', 'eu', 'primary'),
    'changed_port_state_miss': ('us', None, 'us', 'secondary'),
    'wrong_origin_initializer': ('us', None, 'us', 'primary'),
    'missing_only_preserves_change': ('us', 'us', 'us', 'primary'),
    'unconditional_overwrites_change': ('eu', 'eu', 'eu', 'primary'),
    'query_only_without_storage': ('eu', None, 'eu', 'primary'),
    'query_missing_without_storage': ('us', None, 'us', 'primary'),
}
DIAGNOSTICS = {'json_argument_round_trip', 'storage_crud',
               'session_storage_not_restored', 'storage_event_other_page'}
JSON_PAYLOAD = {'label': 'quote " slash \\ newline\n </script>', 'nested': {'enabled': True, 'count': 2}}
