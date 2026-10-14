"""Regression against the numeric example in Arroyo de Humanejos.xlsx."""
import unittest

from flow import concentration_time, rational_flows
from norm52 import NORM_USES


class FlowTest(unittest.TestCase):
    def test_reference_workbook(self):
        tc = concentration_time(10.21485, (699-618.7)/10_214.85)
        self.assertAlmostEqual(tc, 4.405504965244777, places=10)
        result = rational_flows(area_km2=23.87518103, p0_initial=18.733050200457473,
                                cv=.34, mean_daily_rain_mm=37, beta_m=2.15,
                                torrentiality=10, tc_hours=tc,
                                ft={2:.7, 5:.88, 10:.9475, 25:1.15, 50:1.22,
                                    100:1.38, 500:1.62})
        rows = {row['periodo']: row for row in result['periodos']}
        for period, expected in [(5, 1.4305828747815), (100, 5.26639115038557),
                                 (500, 9.18749037238687)]:
            self.assertAlmostEqual(rows[period]['caudal_m3_s'], expected, places=10)
        self.assertEqual(rows[200]['estado'], 'Falta Ft')

    def test_norm_rows_with_same_code_remain_distinct(self):
        self.assertEqual(len(NORM_USES), 177)
        self.assertEqual(NORM_USES['21100-abandonadas'].values, (20, 14, 11, 8))
        self.assertEqual(NORM_USES['21100-hortalizas'].values, (29, 19, 14, 11))
        self.assertEqual(NORM_USES['21100-viveros'].values, (75, 34, 19, 14))
        self.assertEqual(NORM_USES['51220'].values, (0, 0, 0, 0))
        self.assertEqual(NORM_USES['23100-abandonados'].values, (58, 25, 12, 7))
        self.assertEqual(NORM_USES['23100-abandonados-ge3'].values, (24, 14, 8, 6))
        self.assertEqual(NORM_USES['23100-arbolados'].values, (120, 55, 22, 14))


if __name__ == '__main__':
    unittest.main()
