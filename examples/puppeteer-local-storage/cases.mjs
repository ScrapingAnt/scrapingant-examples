export const EXTRACTIONS = {
  fresh_page: { matches: 0, storage: null, region: 'US', source: 'default', requests: 1 },
  pre_app_seed: { matches: 4, storage: 'EU', region: 'EU', source: 'localStorage', requests: 1 },
  late_write_stale_dom: { matches: 0, storage: 'EU', region: 'US', source: 'default', requests: 0 },
  late_write_then_reload: { matches: 4, storage: 'EU', region: 'EU', source: 'localStorage', requests: 1 },
  snapshot_fresh_context: { matches: 4, storage: 'EU', region: 'EU', source: 'localStorage', requests: 1 },
  same_context_new_page: { matches: 4, storage: 'EU', region: 'EU', source: 'localStorage', requests: 1 },
  isolated_context: { matches: 0, storage: null, region: 'US', source: 'default', requests: 1 },
  second_origin_guarded: { matches: 0, storage: null, region: 'US', source: 'default', requests: 1 },
  return_to_original_origin: { matches: 4, storage: 'EU', region: 'EU', source: 'localStorage', requests: 1 },
  query_url_without_storage: { matches: 4, storage: null, region: 'EU', source: 'query', requests: 1 },
  direct_query_without_browser: { matches: 4, storage: null, region: 'EU', source: 'no_browser', requests: 1 },
  direct_missing_query: { matches: 0, storage: null, region: 'US', source: 'no_browser', requests: 1 },
};
export const DIAGNOSTICS = ['about_blank_storage', 'storage_event_handshake', 'node_browser_boundary', 'json_argument_transport'];
export const TRANSPORT_PROBE = {
  text: "quote'\"\\\n雪</script>;window.injected=true;//",
  options: { language: 'uk', enabled: true }, count: 3,
};
