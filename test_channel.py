"""Synthetic D8 basin with a shorter tributary and known channel profile."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from channel import main_channel, save_channel


class ChannelTest(unittest.TestCase):
    def test_longest_upstream_branch_and_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = {'driver': 'GTiff', 'width': 5, 'height': 6, 'count': 1,
                       'crs': 'EPSG:25830', 'transform': from_origin(500000, 4400000, 2, 2)}
            mask = np.zeros((6, 5), dtype='uint8')
            mask[:, 2] = 1
            mask[2, 1] = 1
            pointer = np.zeros_like(mask)
            pointer[:5, 2] = 8  # south
            pointer[2, 1] = 2   # east
            accum = np.zeros((6, 5), dtype='float32')
            accum[:, 2] = [1, 2, 4, 5, 6, 7]
            accum[2, 1] = 1
            dem = np.zeros((6, 5), dtype='float32')
            dem[:, 2] = [110, 108, 106, 104, 102, 100]
            dem[2, 1] = 120
            for name, data in [('cuenca_mascara', mask), ('direccion_d8', pointer),
                               ('acumulacion_celdas', accum), ('mosaico', dem)]:
                with rasterio.open(root/f'{name}.tif', 'w', dtype=data.dtype, **profile) as dst:
                    dst.write(data, 1)
            result = main_channel(*(root/f'{name}.tif' for name in
                                    ('cuenca_mascara', 'direccion_d8', 'acumulacion_celdas', 'mosaico')),
                                  (500005, 4399989), 0.000004)
            self.assertAlmostEqual(result['longitud_m'], 10)
            self.assertEqual(result['celdas_trazado'], 6)
            self.assertEqual((result['cota_max_m'], result['cota_min_m']), (110, 100))
            self.assertEqual((result['cabecera_x'], result['cabecera_y']),
                             (500005, 4399999))
            self.assertEqual((result['cota_cabecera_m'], result['cota_vertido_m']), (110, 100))
            self.assertAlmostEqual(result['pendiente_m_m'], 1)
            self.assertTrue(save_channel(root, result).is_file())

    def test_diagonal_whitebox_pointer_distance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p = {'driver': 'GTiff', 'width': 3, 'height': 3, 'count': 1,
                 'crs': 'EPSG:25830', 'transform': from_origin(500000, 4400000, 2, 2)}
            arrays = {
                'cuenca_mascara': np.array([[1,0,0],[0,1,0],[0,0,0]], dtype='uint8'),
                'direccion_d8': np.array([[4,0,0],[0,0,0],[0,0,0]], dtype='uint8'),
                'acumulacion_celdas': np.array([[1,0,0],[0,2,0],[0,0,0]], dtype='float32'),
                'mosaico': np.array([[10,0,0],[0,8,0],[0,0,0]], dtype='float32')}
            for name, array in arrays.items():
                with rasterio.open(root/f'{name}.tif', 'w', dtype=array.dtype, **p) as dst:
                    dst.write(array, 1)
            result = main_channel(*(root/f'{name}.tif' for name in arrays),
                                  (500003, 4399997), 0.000004)
            self.assertAlmostEqual(result['longitud_m'], 2*np.sqrt(2), places=6)


if __name__ == '__main__':
    unittest.main()
