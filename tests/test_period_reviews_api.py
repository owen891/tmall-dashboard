import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class PeriodReviewsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tmall-dashboard-period-review-tests-')
        from app import create_app
        self.app = create_app({'TESTING': True, 'DATABASE_PATH': os.path.join(self.temp.name, 'dashboard.db')})
        self.client = self.app.test_client()

    def tearDown(self): self.temp.cleanup()

    def test_daily_weekly_monthly_reviews_are_persisted(self):
        response = self.client.put('/api/period-reviews/month/2026-04', json={
            'summary':'月度回顾', 'conclusions':'转化改善', 'next_actions':'保持素材', 'reviewer':'operator',
        })
        self.assertEqual(response.status_code, 200); response.close()
        response = self.client.get('/api/period-reviews?period_type=month')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data'][0]['period_key'], '2026-04')
        self.assertIn('created_at', response.get_json()['data'][0])
        self.assertIn('updated_at', response.get_json()['data'][0])
        response.close()


if __name__ == '__main__': unittest.main(verbosity=2)
