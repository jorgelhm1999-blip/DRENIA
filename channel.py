"""Longest D8 channel within a saved watershed and a flow-accumulation threshold."""
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


def main_channel(basin_file: Path, pointer_file: Path, accumulation_file: Path,
                 dem_file: Path, outlet: tuple[float, float], threshold_km2: float) -> dict:
    """Find the longest connected upstream stream path ending at the adjusted outlet."""
    if threshold_km2 <= 0:
        raise ValueError('El área mínima de cauce debe ser positiva.')
    with (rasterio.open(basin_file) as basin, rasterio.open(pointer_file) as pointer,
          rasterio.open(accumulation_file) as accum, rasterio.open(dem_file) as dem):
        if any((x.shape != basin.shape or x.transform != basin.transform or x.crs != basin.crs)
               for x in (pointer, accum, dem)):
            raise ValueError('Máscara, dirección, acumulación y MDT no comparten retícula.')
        win = _basin_window(basin)
        h, w = int(win.height), int(win.width)
        if h*w > 80_000_000:
            raise ValueError('La extensión de esta cuenca requiere más memoria para analizar el cauce.')
        inside = basin.read(1, window=win) > 0
        acc = accum.read(1, window=win)
        codes = pointer.read(1, window=win).astype(np.uint8)
        elevation = dem.read(1, window=win)
        cell_area = abs(basin.transform.a*basin.transform.e)
        stream = inside & np.isfinite(acc) & (acc >= threshold_km2*1e6/cell_area)
        row, col = basin.index(*outlet)
        rr, cc = row-int(win.row_off), col-int(win.col_off)
        if not (0 <= rr < h and 0 <= cc < w and stream[rr, cc]):
            raise ValueError('El vertido ajustado no está en la red de cauces para este umbral. Reduce el área mínima drenada.')
        locations = np.flatnonzero(stream)
        if len(locations) < 2:
            raise ValueError('La red seleccionada no contiene un tramo de cauce aguas arriba del vertido.')
        sorted_cells = locations[np.argsort(acc.flat[locations], kind='stable')]
        score = np.zeros((h, w), dtype=np.float32)
        parent = np.full((h, w), -1, dtype=np.int32)
        dx, dy = abs(basin.transform.a), abs(basin.transform.e)
        for index in sorted_cells:
            r, c = divmod(int(index), w)
            offset = _OFFSETS.get(int(codes[r, c]))
            if offset is None:
                continue
            dr, dc = offset
            nr, nc = r+dr, c+dc
            if (0 <= nr < h and 0 <= nc < w and stream[nr, nc]
                    and acc[nr, nc] > acc[r, c]):
                candidate = float(score[r, c]) + math.hypot(dc*dx, dr*dy)
                if candidate > score[nr, nc]:
                    score[nr, nc] = candidate
                    parent[nr, nc] = index
        outlet_index = rr*w+cc
        indices = [outlet_index]
        while parent.flat[indices[-1]] >= 0:
            indices.append(int(parent.flat[indices[-1]]))
            if len(indices) > len(locations):
                raise ValueError('Se ha detectado un bucle en la dirección de flujo.')
        if len(indices) < 2:
            raise ValueError('No se ha encontrado un cauce conectado aguas arriba del vertido.')
        indices.reverse()
        heights = elevation.flat[indices]
        if not np.isfinite(heights).all() or np.any(heights == dem.nodata):
            raise ValueError('El cauce cruza cotas sin datos en el MDT.')
        length = float(score[rr, cc])
        slope = (float(np.max(heights))-float(np.min(heights)))/length
        transform = basin.window_transform(win)
        coords = [list(rasterio.transform.xy(transform, idx//w, idx%w)) for idx in indices]
        return {'longitud_m': length, 'longitud_km': length/1000,
                'cota_max_m': float(np.max(heights)), 'cota_min_m': float(np.min(heights)),
                'cota_cabecera_m': float(heights[0]), 'cota_vertido_m': float(heights[-1]),
                'pendiente_m_m': slope, 'tc_h': concentration_time(length/1000, slope),
                'umbral_cauce_km2': threshold_km2, 'celdas_trazado': len(indices),
                'geometry': {'type': 'LineString', 'coordinates': coords},
                'crs': basin.crs.to_string()}


def save_channel(folder: Path, result: dict) -> Path:
    path = Path(folder)/'cauce_principal.geojson'
    geographic = transform_geom(result['crs'], 'EPSG:4326', result['geometry'])
    path.write_text(json.dumps({'type': 'FeatureCollection',
        'features': [{'type': 'Feature', 'geometry': geographic,
                      'properties': {k: v for k, v in result.items() if k not in ('geometry', 'crs')}}]},
        ensure_ascii=False), encoding='utf-8')
    return path
