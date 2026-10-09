import copy
import unittest

from contract import assess, summary, schedule, api_parameters, reserve

STATIC = '<table id="prices"><tbody>' + ''.join(
    '<tr>' + ''.join('<td>' + c + '</td>' for c in row) + '</tr>'
    for row in [
        ['Ant Farm Deluxe', '$1,234.50', '12,345', '45.5%'],
        ['Ant Farm Mini', '$99.00', '1,020', '3.8%'],
        ['Magnifier', '$12.25', '987,654', '50.7%'],
    ]) + '</tbody></table>'
DELAYED = '<div id="test">I ❤️ ScrapingAnt (after 1500 ms)</div><div id="loaded">loaded</div>'


class ContractTests(unittest.TestCase):
    def test_exact_static_records(self):
        self.assertEqual(assess('static', STATIC, 200, 200)['valid_records'], 3)

    def test_wrong_price_fails_whole_contract(self):
        self.assertEqual(assess('static', STATIC.replace('$99.00', '$98.00'), 200, 200)['valid_records'], 0)

    def test_missing_and_extra_rows_fail(self):
        for body in (STATIC.replace('<td>Magnifier</td>', ''), STATIC.replace('</tbody>', '<tr><td>extra</td></tr></tbody>')):
            self.assertFalse(assess('static', body, 200, 200)['valid'])

    def test_duplicate_tables_fail(self):
        self.assertFalse(assess('static', STATIC + STATIC, 200, 200)['valid'])

    def test_status_failure_not_valid_even_with_right_html(self):
        for status, target in [(500, 200), (200, 404), (200, None)]:
            self.assertFalse(assess('static', STATIC, status, target)['valid'])

    def test_delayed_content_requires_ready_marker_and_exact_text(self):
        self.assertTrue(assess('delayed', DELAYED, 200, 200)['valid'])
        for body in (DELAYED.replace('id="loaded"', 'id="wrong"'), DELAYED.replace('I ❤️ ScrapingAnt (after 1500 ms)', 'Web Scraping is hard'), DELAYED + DELAYED):
            self.assertFalse(assess('delayed', body, 200, 200)['valid'])

    def rows(self):
        return [dict(target='static', arm='api_raw', round=i, valid=i == 0,
                     valid_records=3 if i == 0 else 0, elapsed_ms=10 + i,
                     credits=1, outcome='valid' if i == 0 else 'invalid_contract') for i in range(2)]

    def test_charged_invalid_response_stays_in_numerator(self):
        result = summary(self.rows())[0]
        self.assertEqual(result['credits_total'], 2)
        self.assertEqual(result['credits_per_valid_record'], 2/3)
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(result['median_all_ms'], 10.5)

    def test_missing_receipt_means_unknown_cost(self):
        rows = self.rows(); rows[1]['credits'] = None
        self.assertIsNone(summary(rows)[0]['credits_per_valid_record'])

    def test_zero_valid_is_undefined_not_free(self):
        rows = self.rows(); rows[0].update(valid=False, valid_records=0)
        self.assertIsNone(summary(rows)[0]['credits_per_valid_record'])

    def test_schedule_retains_each_target_arm_round(self):
        plan = schedule(['requests', 'playwright', 'api_raw', 'api_rendered'], 10, 607)
        self.assertEqual(len(plan), 80)
        self.assertEqual(len(set(plan)), 80)
        self.assertEqual(plan, schedule(['requests', 'playwright', 'api_raw', 'api_rendered'], 10, 607))
        self.assertNotEqual(plan, schedule(['requests', 'playwright', 'api_raw', 'api_rendered'], 10, 608))

    def test_rendered_has_selector_and_source_false_raw_does_not(self):
        rendered = api_parameters('static', 'api_rendered', 'https://example.test')
        self.assertEqual(rendered['return_page_source'], 'false')
        self.assertEqual(rendered['wait_for_selector'], '#prices tbody tr')
        self.assertNotIn('wait_for_selector', api_parameters('static', 'api_raw', 'https://example.test'))

    def test_budget_reserves_before_call(self):
        self.assertEqual(reserve(220, 210, 'api_rendered'), 10)
        with self.assertRaises(ValueError):
            reserve(220, 211, 'api_rendered')


if __name__ == '__main__':
    unittest.main()
