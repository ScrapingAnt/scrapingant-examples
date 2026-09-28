"""Independently specified expected wrong outputs, alongside target outputs."""
from oracle import EXPECTED, OUTSIDE, INACTIVE

EXTRACTION = {
    'first_scoped': {'records': EXPECTED[:1], 'error': None, 'target': False},
    'all_scoped_css': {'records': EXPECTED, 'error': None, 'target': True},
    'relative_xpath': {'records': EXPECTED, 'error': None, 'target': True},
    'unscoped_css': {'records': (OUTSIDE,) + EXPECTED, 'error': None, 'target': False},
    'class_token': {'records': EXPECTED, 'error': None, 'target': True},
    'class_substring_wrong': {'records': EXPECTED + (INACTIVE,), 'error': None, 'target': False},
    'presence_only': {'records': (
        ('C-101', '', '', '', '', None),
        ('T-202', '', '', '', '', None),
        ('N-303', '', '', '', '', None),
    ), 'error': None, 'target': False},
    'complete_records_wait': {'records': EXPECTED, 'error': None, 'target': True},
    'stale_handle': {'records': (), 'error': 'StaleElementReferenceException', 'target': False},
    'refind_after_replacement': {'records': EXPECTED, 'error': None, 'target': True},
    'iframe_context': {'records': EXPECTED, 'error': None, 'target': True},
    'open_shadow_root': {'records': EXPECTED, 'error': None, 'target': True},
}
DIAGNOSTICS = {
    'missing_singular': {'error': 'NoSuchElementException'},
    'missing_plural': {'count': 0},
    'compound_class_name': {'error': 'InvalidSelectorException'},
    'text_boundaries': {'visible_text': 'Visible', 'text_content': 'VisibleHidden'},
    'attribute_property': {
        'value_attribute': 'initial', 'value_property': 'edited',
        'value_get_attribute': 'edited', 'href_attribute': '/products/cafe',
        'href_property_is_absolute_loopback': True,
    },
}
