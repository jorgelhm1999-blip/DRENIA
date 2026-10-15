"""Hydraulically remotest basin cell by D8 path length to the outlet."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform_geom

from flow import concentration_time


# WhiteboxTools clockwise pointer convention (NOT the ESRI D8 convention).
_OFFSETS = {1: (-1, 1), 2: (0, 1), 4: (1, 1), 8: (1, 0),
            16: (1, -1), 32: (0, -1), 64: (-1, -1), 128: (-1, 0)}


def _basin_window(ds):
    r0, c0, r1, c1 = ds.height, ds.width, -1, -1
    for _, window in ds.block_windows(1):
        data = ds.read(1, window=window)
        rows, cols = np.nonzero(data > 0)
        if rows.size:
            r0 = min(r0, int(window.row_off) + int(rows.min()))
            c0 = min(c0, int(window.col_off) + int(cols.min()))
            r1 = max(r1, int(window.row_off) + int(rows.max()))
            c1 = max(c1, int(window.col_off) + int(cols.max()))
    if r1 < r0:
        raise ValueError('La máscara de la cuenca está vacía.')
    return Window(c0, r0, c1-c0+1, r1-r0+1)


METHOD = 'longest_d8_basin_path_v1'


def hydrological_path(basin_file: Path, pointer_file: Path, accumulation_file: Path,
                      dem_file: Path, outlet: tuple[float, float]) -> dict:
    """Find the longest D8 path ending at the outlet, considering every basin cell."""
    with (rasterio.open(basin_file) as basin, rasterio.open(pointer_file) as pointer,
          rasterio.open(accumulation_file) as accum, rasterio.open(dem_file) as dem):
        if any((x.shape != basin.shape or x.transform != basin.transform or x.crs != basin.crs)
               for x in (pointer, accum, dem)):
            raise ValueError('Máscara, dirección, acumulación y MDT no comparten retícula.')
        win = _basin_window(basin)
        h, w = int(win.height), int(win.width)
        if h*w > 40_000_000:
            raise ValueError('La extensión de esta cuenca requiere más memoria para analizar todos los recorridos D8.')
        inside = basin.read(1, window=win) > 0
        acc = accum.read(1, window=win)
        codes = pointer.read(1, window=win).astype(np.uint8)
        elevation = dem.read(1, window=win)
        row, col = basin.index(*outlet)
        rr, cc = row-int(win.row_off), col-int(win.col_off)
        if not (0 <= rr < h and 0 <= cc < w and inside[rr, cc]):
            raise ValueError('El vertido ajustado no está dentro de la máscara de la cuenca.')
        locations = np.flatnonzero(inside & np.isfinite(acc) & (acc > 0))
        if len(locations) < 2:
            raise ValueError('La cuenca no contiene un recorrido D8 aguas arriba del vertido.')
        # A downstream cell receives strictly more contributing cells than its donors.
        # Visiting in descending accumulation makes its distance to the outlet available.
        sorted_cells = locations[np.argsort(acc.flat[locations], kind='stable')[::-1]]
        distance = np.full((h, w), -1, dtype=np.float32)
        distance[rr, cc] = 0
        dx, dy = abs(basin.transform.a), abs(basin.transform.e)
        for index in sorted_cells:
            r, c = divmod(int(index), w)
            if r == rr and c == cc:
                continue
            offset = _OFFSETS.get(int(codes[r, c]))
            if offset is None:
                continue
            dr, dc = offset
            nr, nc = r+dr, c+dc
            if (0 <= nr < h and 0 <= nc < w and inside[nr, nc]
                    and acc[nr, nc] > acc[r, c] and distance[nr, nc] >= 0):
                distance[r, c] = distance[nr, nc] + math.hypot(dc*dx, dr*dy)
        unreachable = int(np.count_nonzero(inside & (distance < 0)))
        if unreachable:
            raise ValueError(f'{unreachable} celdas de la cuenca no llegan al vertido siguiendo el D8 guardado; '
                             'revisa que la máscara y la dirección pertenezcan a la misma pasada.')
        head_index = int(np.argmax(distance))
        length = float(distance.flat[head_index])
        indices = [head_index]
        while indices[-1] != rr*w+cc:
            r, c = divmod(indices[-1], w)
            offset = _OFFSETS.get(int(codes[r, c]))
            if offset is None:
                raise ValueError('El recorrido D8 se interrumpe antes de alcanzar el vertido.')
            nr, nc = r+offset[0], c+offset[1]
            if not (0 <= nr < h and 0 <= nc < w):
                raise ValueError('El recorrido D8 sale de la cuenca antes del vertido.')
            indices.append(nr*w+nc)
            if len(indices) > len(locations):
                raise ValueError('Se ha detectado un bucle en la dirección de flujo.')
        if len(indices) < 2:
            raise ValueError('No se ha encontrado una trayectoria aguas arriba del vertido.')
        heights = elevation.flat[indices]
        if not np.isfinite(heights).all() or (dem.nodata is not None and np.any(heights == dem.nodata)):
            raise ValueError('La trayectoria cruza cotas sin datos en el MDT.')
        drop = float(heights[0])-float(heights[-1])
        slope = drop/length
        transform = basin.window_transform(win)
        coords = [list(rasterio.transform.xy(transform, idx//w, idx%w)) for idx in indices]
        return {'longitud_m': length, 'longitud_km': length/1000,
                'cabecera_x': coords[0][0], 'cabecera_y': coords[0][1],
                'cota_max_m': float(np.max(heights)), 'cota_min_m': float(np.min(heights)),
                'cota_cabecera_m': float(heights[0]), 'cota_vertido_m': float(heights[-1]),
                'desnivel_m': drop, 'pendiente_m_m': slope,
                'tc_h': concentration_time(length/1000, slope) if slope > 0 else None,
                'metodo': METHOD, 'celdas_trazado': len(indices),
                'geometry': {'type': 'LineString', 'coordinates': coords},
                'crs': basin.crs.to_string()}


def save_channel(folder: Path, result: dict) -> Path:
    path = Path(folder)/'recorrido_hidrologico.geojson'
    geographic = transform_geom(result['crs'], 'EPSG:4326', result['geometry'])
    path.write_text(json.dumps({'type': 'FeatureCollection',
        'features': [{'type': 'Feature', 'geometry': geographic,
                      'properties': {k: v for k, v in result.items() if k not in ('geometry', 'crs')}}]},
        ensure_ascii=False), encoding='utf-8')
    return path
