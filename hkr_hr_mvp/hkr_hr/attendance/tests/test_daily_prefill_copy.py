import unittest
from hkr_hr.app.words import TRANSLATIONS


class DailyPrefillCopyTests(unittest.TestCase):
    def test_prefill_is_an_assumption_not_a_sunday_pay_exclusion(self):
        for language, assumption, actual in (
            ('zh-Hant', '預填暫按星期日不上班', '包含真正上班的星期日'),
            ('zh-Hans', '预填暂按星期日不上班', '包含真正上班的星期日'),
            ('en', 'Prefill assumes Sundays off', 'including worked Sundays'),
        ):
            with self.subTest(language=language):
                messages = TRANSLATIONS[language]
                self.assertIn(assumption, messages['attendance.prefill_daily_actual'])
                self.assertIn(assumption, messages['attendance.prefill_daily_forecast'])
                self.assertIn(actual, messages['attendance.daily_working_days_hint'])
                self.assertIn('Sunday' if language == 'en' else '星期日', messages['attendance.daily_forecast_working_hint'])


if __name__ == '__main__':
    unittest.main()
