"""Fast independent checks for the rainfall table and polygon clipping."""
import tempfile
import unittest
from pathlib import Path

import fiona
from shapely.geometry import box, mapping

from landuse import landuse_summary, yt_factors
from norm52 import DEFAULT_EQUIVALENCES, threshold_summary


class LanduseTest(unittest.TestCase):
    def test_yt_lookup_interpolation_and_bounds(self):
        self.assertEqual((yt_factors(.34)[5], yt_factors(.34)[100], yt_factors(.34)[500]),
                         (1.213, 2.174, 2.785))
        self.assertEqual(yt_factors(.325)[5], 1.2055)
        with self.assertRaises(ValueError):
            yt_factors(.53)

    def test_clip_exact_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            basin = Path(directory) / 'cuenca.gpkg'
            uses = Path(directory) / 'usos.gpkg'
            with fiona.open(basin, 'w', driver='GPKG', layer='cuenca', crs='EPSG:25830',
                            schema={'geometry': 'Polygon', 'properties': {'id': 'int'}}) as out:
                out.write({'geometry': mapping(box(0, 0, 100, 100)), 'properties': {'id': 1}})
            with fiona.open(uses, 'w', driver='GPKG', crs='EPSG:25830',
                            schema={'geometry': 'Polygon',
                                    'properties': {'TC_SIOSE_C': 'str'}}) as out:
                out.write({'geometry': mapping(box(-10, 0, 50, 100)),
                           'properties': {'TC_SIOSE_C': 'Ensanche'}})
                out.write({'geometry': mapping(box(50, 0, 110, 100)),
                           'properties': {'TC_SIOSE_C': 'Zona verde urbana'}})
            result = landuse_summary(basin, uses)
            self.assertEqual(result['cuenca_m2'], 10_000)
            self.assertEqual(result['usos_m2'], 10_000)
            self.assertEqual({x['uso']: x['m2'] for x in result['superficies']},
                             {'Ensanche': 5_000, 'Zona verde urbana': 5_000})
            areas = {x['uso']: x['m2'] for x in result['superficies']}
            threshold = threshold_summary(areas, 'B', DEFAULT_EQUIVALENCES)
            self.assertEqual(threshold['p0_inicial_ponderado_mm'], 18.5)
            self.assertEqual(threshold_summary(areas, 'A', DEFAULT_EQUIVALENCES)
                             ['p0_inicial_ponderado_mm'], 38.5)

    def test_ambiguous_equivalence_is_not_guessed(self):
        result = threshold_summary({'Cultivo herbáceo': 1000}, 'B', DEFAULT_EQUIVALENCES)
        self.assertIsNone(result['p0_inicial_ponderado_mm'])
        self.assertEqual(result['area_sin_equivalencia_m2'], 1000)
        dry = threshold_summary({'Cultivo herbáceo · secano': 1000}, 'B', DEFAULT_EQUIVALENCES)
        self.assertEqual(dry['p0_inicial_ponderado_mm'], 21)


if __name__ == '__main__':
    unittest.main()
