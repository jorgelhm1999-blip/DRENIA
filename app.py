"""Small offline desktop GUI for guided watershed delineation."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
import math
import json
import re
import sys
import time
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageTk
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from engine import (compare_basins, delineate, index_tiles, locate_whitebox,
                    neighboring_tiles, open_saved_result, prepare_hydrology, snap_to_stream)
from ortho import local_ortho_image, pnoa_image
from diagnostics import diagnostic_preview
from landuse import landuse_summary, save_landuse_summary, yt_factors
from flow import FLOW_PERIODS
from norm52 import DEFAULT_EQUIVALENCES, GROUPS, NORM_USES, threshold_summary
from flow import concentration_time, rational_flows, parse_ft
from channel import METHOD, hydrological_path, save_channel
from excel_report import export_excel as write_excel_report


class Window(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('DRENIA · Delimitación de cuencas')
        icon = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'assets' / 'drenia_kyogre.ico'
        if icon.exists():
            self.iconbitmap(str(icon))
        self.geometry('1250x860')
        self.minsize(980, 730)
        self.tiles = []
        self.preview = None
        self.preview_bounds = None
        self.overlay = None
        self.stream_overlay = None
        self.accum_path = None
        self.hydro_folder = None
        self.diagnostic_images = {}
        self.diagnostic_generation = 0
        self.ortho_preview = None
        self.ortho_source = 'PNOA'
        self.ortho_generation = 0
        self.current_crs = None
        self.last_run = None
        self.audit_candidates = []
        self.outlet = None
        self.result_outlet = None
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0.0
        self.drag_start = None
        self.image_ref = None
        self.events = queue.Queue()
        self.busy = False
        self.started_at = None
        self.last_activity = None
        self.phase = ''
        self.channel_generation = 0
        self.channel_head = None
        self.channel_route = None
        self.folder = tk.StringVar()
        self.output = tk.StringVar()
        self.binary = tk.StringVar()
        self.radius = tk.StringVar(value='6')
        self.breach = tk.StringVar(value='50')
        self.selection = tk.StringVar()
        self.x_coord = tk.StringVar()
        self.y_coord = tk.StringVar()
        self.threshold = tk.StringVar(value='0,05')
        self.transparency = tk.IntVar(value=0)
        self.audit_selection = tk.StringVar()
        self.view_mode = tk.StringVar(value='MDT')
        self._layout()
        self.after(120, self._poll)

    def _layout(self):
        left = ttk.Frame(self, padding=14)
        left.pack(side='left', fill='y')
        left.configure(width=335)
        left.pack_propagate(False)
        ttk.Label(left, text='DRENIA', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(left, text='MDT local · Cauces y cuenca desde un vertido',
                  wraplength=300).pack(anchor='w', pady=(1, 6))
        self._heading(left, '1  Carpeta y tesela inicial')
        ttk.Entry(left, textvariable=self.folder).pack(fill='x', pady=(3, 3))
        ttk.Button(left, text='Elegir carpeta de MDT', command=self.pick_folder).pack(fill='x')
        self.tile_box = ttk.Combobox(left, state='readonly', textvariable=self.selection)
        self.tile_box.pack(fill='x', pady=(9, 2))
        self.tile_box.bind('<<ComboboxSelected>>', lambda e: self.load_preview())
        ttk.Label(left, text='Solo TIFF con retícula compatible y CRS en metros.',
                  wraplength=300, foreground='#586575').pack(anchor='w')
        self._heading(left, '2  Mostrar cauces calculados')
        threshold_line = ttk.Frame(left)
        threshold_line.pack(fill='x', pady=(5, 4))
        ttk.Label(threshold_line, text='Área mínima drenada (km²)').pack(side='left')
        ttk.Spinbox(threshold_line, from_=0.0001, to=1000, increment=0.01, width=9,
                    textvariable=self.threshold).pack(side='right')
        self.network_button = ttk.Button(left, text='Calcular y mostrar cauces', command=self.prepare)
        self.network_button.pack(fill='x', pady=(1, 3))
        ttk.Button(left, text='Actualizar umbral de cauces',
                   command=self.refresh_stream_overlay).pack(fill='x')
        ttk.Label(left, text='La red inicial usa esta tesela; al delimitar se incorporan las vecinas necesarias.',
                  wraplength=300, foreground='#586575').pack(anchor='w', pady=(3, 0))
        self._heading(left, '3  Punto de vertido')
        ttk.Label(left, text='Haz clic sobre un cauce azul o introduce coordenadas del CRS del MDT.',
                  wraplength=300).pack(anchor='w', pady=(3, 3))
        coords = ttk.Frame(left)
        coords.pack(fill='x', pady=(2, 3))
        ttk.Label(coords, text='X').grid(row=0, column=0)
        ttk.Entry(coords, textvariable=self.x_coord, width=11).grid(row=0, column=1, padx=(2, 8))
        ttk.Label(coords, text='Y').grid(row=0, column=2)
        ttk.Entry(coords, textvariable=self.y_coord, width=11).grid(row=0, column=3, padx=(2, 0))
        ttk.Button(left, text='Situar punto por coordenadas', command=self.go_coordinates).pack(fill='x')
        self.point_label = ttk.Label(left, text='Sin seleccionar', foreground='#657280')
        self.point_label.pack(anchor='w', pady=(3, 0))
        line = ttk.Frame(left)
        line.pack(fill='x', pady=(8, 0))
        ttk.Label(line, text='Radio de ajuste (m)').pack(side='left')
        ttk.Spinbox(line, from_=0, to=1000, increment=2, width=8,
                    textvariable=self.radius).pack(side='right')
        line2 = ttk.Frame(left)
        line2.pack(fill='x', pady=(5, 0))
        ttk.Label(line2, text='Búsqueda de brecha (celdas)').pack(side='left')
        ttk.Spinbox(line2, from_=1, to=1000, increment=10, width=8,
                    textvariable=self.breach).pack(side='right')
        self._heading(left, '4  Calcular y guardar')
        ttk.Entry(left, textvariable=self.output).pack(fill='x', pady=(4, 3))
        ttk.Button(left, text='Elegir carpeta de resultados', command=self.pick_output).pack(fill='x')
        self.calculate = ttk.Button(left, text='Delimitar cuenca', command=self.start)
        self.calculate.pack(fill='x', pady=(12, 5), ipady=7)
        ttk.Button(left, text='Abrir análisis guardado…', command=self.pick_saved_result).pack(fill='x')
        ttk.Button(left, text='Usos, precipitación y caudales…',
                   command=self.show_landuse).pack(fill='x', pady=(5, 0))
        self.status = tk.StringVar(value='Elige una carpeta con teselas GeoTIFF.')
        ttk.Label(left, textvariable=self.status, wraplength=300,
                  foreground='#11645d').pack(anchor='w', pady=(3, 0))
        self.timer_status = tk.StringVar(value='')
        ttk.Label(left, textvariable=self.timer_status, wraplength=300,
                  foreground='#486378').pack(anchor='w', pady=(3, 0))
        self.channel_summary = tk.StringVar(value='Cabecera hidrológica: disponible después de delimitar la cuenca.')
        ttk.Label(left, textvariable=self.channel_summary, wraplength=300,
                  foreground='#254d78').pack(anchor='w', pady=(7, 0))
        ttk.Separator(left).pack(fill='x', pady=13)
        ttk.Label(left, text='Motor hidrológico (WhiteboxTools)',
                  font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        ttk.Entry(left, textvariable=self.binary).pack(fill='x', pady=(4, 2))
        ttk.Button(left, text='Localizar ejecutable…', command=self.pick_binary).pack(fill='x')
        ttk.Label(left, text='Se detecta automáticamente en la versión descargada. Déjalo vacío.',
                  wraplength=300, foreground='#586575').pack(anchor='w', pady=(3, 0))

        right = ttk.Frame(self, padding=(2, 14, 14, 10))
        right.pack(side='right', expand=True, fill='both')
        ttk.Label(right, text='Vista del MDT', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(right, text='Azul: drenaje del MDT · Rueda: acercar · Arrastrar: mover · Clic: vertido',
                  foreground='#586575').pack(anchor='w', pady=(0, 5))
        views = ttk.Frame(right)
        views.pack(fill='x', pady=(0, 5))
        for mode in ('MDT', 'Dirección D8', 'Acumulación'):
            ttk.Radiobutton(views, text=mode, variable=self.view_mode, value=mode,
                            command=self.select_view).pack(side='left', padx=(0, 12))
        self.view_note = ttk.Label(views, text='Altitud (m)', foreground='#586575')
        self.view_note.pack(side='right')
        map_tools = ttk.Frame(right)
        map_tools.pack(fill='x', pady=(0, 5))
        ttk.Button(map_tools, text='PNOA', command=self.choose_pnoa).pack(side='left', padx=(0, 5))
        ttk.Button(map_tools, text='Ortofoto local…', command=self.choose_local_ortho).pack(side='left')
        ttk.Label(map_tools, text='Transparencia ortofoto  0%').pack(side='left', padx=(14, 2))
        tk.Scale(map_tools, variable=self.transparency, from_=0, to=100, orient='horizontal',
                 length=170, showvalue=False, command=lambda v: self.draw()).pack(side='left')
        ttk.Label(map_tools, text='100%').pack(side='left')
        self.canvas = tk.Canvas(right, background='#e6eaec', highlightthickness=0, cursor='crosshair')
        self.canvas.pack(expand=True, fill='both')
        self.canvas.bind('<Configure>', lambda e: self.draw())
        self.canvas.bind('<MouseWheel>', self.wheel)
        self.canvas.bind('<Button-4>', lambda e: self.change_zoom(1.2, e.x, e.y))
        self.canvas.bind('<Button-5>', lambda e: self.change_zoom(1/1.2, e.x, e.y))
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        audit = ttk.Frame(right)
        audit.pack(fill='x', pady=(8, 3))
        ttk.Label(audit, text='Comprobar teselas vecinas:').pack(side='left', padx=(0, 6))
        self.audit_box = ttk.Combobox(audit, state='readonly', textvariable=self.audit_selection, width=43)
        self.audit_box.pack(side='left', padx=(0, 6))
        self.audit_button = ttk.Button(audit, text='Auditar y comparar', command=self.audit,
                                       state='disabled')
        self.audit_button.pack(side='left')
        ttk.Label(right, text='Proceso', font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(10, 3))
        self.log = tk.Text(right, height=7, state='disabled', wrap='word', font=('Consolas', 9))
        self.log.pack(fill='x')

    @staticmethod
    def _heading(parent, title):
        ttk.Label(parent, text=title, font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(14, 0))

    def _log(self, line):
        self.log.configure(state='normal')
        self.log.insert('end', line + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def _start_clock(self, phase):
        self.started_at = self.last_activity = time.monotonic()
        self.phase = phase

    def _stop_clock(self):
        if self.started_at is not None:
            elapsed = int(time.monotonic() - self.started_at)
            self.timer_status.set(f'Tiempo de cálculo: {elapsed//60:02d}:{elapsed%60:02d}')
        self.started_at = None

    def _update_clock(self):
        if self.started_at is None:
            return
        now = time.monotonic()
        elapsed = int(now - self.started_at)
        silence = int(now - self.last_activity)
        self.timer_status.set(f'{self.phase} · {elapsed//60:02d}:{elapsed%60:02d} transcurridos · '
                              f'{silence//60:02d}:{silence%60:02d} sin noticias del motor')

    def _load_channel(self, destination, result):
        self.channel_generation += 1
        generation = self.channel_generation
        self.channel_head = None
        self.channel_route = None
        self.channel_summary.set('Calculando el punto hidráulicamente más remoto de toda la cuenca…')
        self.draw()

        def worker():
            try:
                work = Path(result['directorio_final'])
                files = [destination/'cuenca_mascara.tif', work/'direccion_d8.tif',
                         work/'acumulacion_celdas.tif', work/'mosaico.tif']
                fingerprint = [(p.stat().st_size, p.stat().st_mtime_ns) for p in files]
                cache = destination/'recorrido_hidrologico_metricas.json'
                metrics = None
                if cache.is_file():
                    saved = json.loads(cache.read_text(encoding='utf-8'))
                    if (saved.get('metodo') == METHOD and 'geometry' in saved and
                            saved.get('punto_vertido') == result['punto_ajustado'] and
                            saved.get('fuentes') == [list(x) for x in fingerprint]):
                        metrics = saved
                if metrics is None:
                    metrics = hydrological_path(*files, tuple(result['punto_ajustado']))
                    metrics['punto_vertido'] = result['punto_ajustado']
                    metrics['fuentes'] = fingerprint
                    save_channel(destination, metrics)
                    cache.write_text(json.dumps(metrics, ensure_ascii=False), encoding='utf-8')
                self.events.put(('main_channel_ready', (generation, metrics)))
            except Exception as exc:
                self.events.put(('main_channel_error', (generation, str(exc))))
        threading.Thread(target=worker, daemon=True).start()

    def pick_folder(self):
        path = filedialog.askdirectory(title='Carpeta con MDT')
        if not path: return
        self.folder.set(path)
        self.tiles, errors = index_tiles(Path(path))
        self.tile_box['values'] = [str(t.path.relative_to(Path(path))) for t in self.tiles]
        self._log(f'{len(self.tiles)} teselas indexadas en {path}.')
        for err in errors[:10]: self._log('Se omite ' + err)
        if self.tiles:
            self.tile_box.current(0)
            self.load_preview()
        else:
            messagebox.showwarning('Sin MDT', 'No hay GeoTIFF válidos con coordenadas en metros.')

    def pick_output(self):
        path = filedialog.askdirectory(title='Carpeta de resultados')
        if path: self.output.set(path)

    def pick_saved_result(self):
        if self.busy:
            return
        folder = filedialog.askdirectory(title='Carpeta con resultado.json y cuenca_mascara.tif')
        if folder:
            try:
                self.restore_saved_result(Path(folder))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                messagebox.showerror('No se pudo abrir el análisis', str(exc))

    def show_landuse(self):
        if not self.last_run and not (Path(self.output.get())/'cuenca.gpkg').is_file():
            messagebox.showinfo('Falta la cuenca', 'Delimita o abre primero un análisis guardado.')
            return
        folder = Path(self.output.get())
        config = folder/'config_analisis.json'
        try:
            saved_config = json.loads(config.read_text(encoding='utf-8')) if config.is_file() else {}
        except (OSError, ValueError):
            saved_config = {}
        report_dir = tk.StringVar(value=saved_config.get('carpeta_informes', str(folder)))
        window = tk.Toplevel(self)
        window.title('DRENIA · YT, superficies y umbral de escorrentía')
        window.geometry('1000x700')
        window.transient(self)
        frame = ttk.Frame(window, padding=14)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Factores YT de máximas lluvias diarias',
                  font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Tabla aportada: Cv 0,30–0,52. Valores intermedios por interpolación lineal.').pack(anchor='w')
        cv = tk.StringVar(value=saved_config.get('cv', '0,34'))
        row = ttk.Frame(frame)
        row.pack(fill='x', pady=(8, 3))
        ttk.Label(row, text='Cv').pack(side='left')
        ttk.Entry(row, textvariable=cv, width=10).pack(side='left', padx=8)
        factors = ttk.Label(frame, text='', wraplength=630, justify='left')
        factors.pack(anchor='w', pady=(0, 14))

        def update_factors(*_):
            try:
                values = yt_factors(float(cv.get().replace(',', '.')))
                factors.configure(text='     '.join(f'T{t}: {values[t]:.3f}' for t in (2, 5, 10, 25)) +
                                  '\n' + '     '.join(f'T{t}: {values[t]:.3f}' for t in (50, 100, 200, 500)))
            except ValueError as exc:
                factors.configure(text=str(exc))
        cv.trace_add('write', update_factors)
        update_factors()
        ttk.Separator(frame).pack(fill='x', pady=8)
        ttk.Label(frame, text='Superficies dentro de la cuenca',
                  font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        source = tk.StringVar(value=saved_config.get('fuente_usos', ''))
        ttk.Entry(frame, textvariable=source).pack(fill='x', pady=(8, 3))
        ttk.Button(frame, text='Elegir GeoPackage de usos…',
                   command=lambda: source.set(filedialog.askopenfilename(parent=window,
                                      filetypes=[('GeoPackage', '*.gpkg')]) or source.get())).pack(anchor='w')
        ttk.Label(frame, text='Corte vectorial exacto. Equivalencias revisables de la tabla 2.3; pendiente <3 % y práctica R/N cuando procedan.',
                  wraplength=800).pack(anchor='w', pady=7)
        run = ttk.Button(frame, text='Calcular superficies', state='normal')
        run.pack(anchor='w', pady=4)
        status = tk.StringVar(value='Selecciona el GeoPackage de usos del suelo.')
        ttk.Label(frame, textvariable=status, wraplength=800).pack(anchor='w')
        group = tk.StringVar(value='B')
        soil = ttk.Frame(frame)
        soil.pack(fill='x', pady=(8, 2))
        ttk.Label(soil, text='Grupo hidrológico de suelo').pack(side='left')
        ttk.Combobox(soil, textvariable=group, values=GROUPS, state='readonly', width=5).pack(side='left', padx=8)
        p0_label = tk.StringVar(value='P₀ inicial ponderado: pendiente de clasificar')
        ttk.Label(soil, textvariable=p0_label).pack(side='left', padx=10)
        table = ttk.Treeview(frame, columns=('uso', 'ha', 'norma', 'p0'), show='headings')
        table.heading('uso', text='Uso del suelo')
        table.heading('ha', text='Superficie (ha)')
        table.heading('norma', text='Fila 5.2-IC')
        table.heading('p0', text='P₀ⁱ (mm)')
        table.column('uso', width=300)
        table.column('ha', width=130, anchor='e')
        table.column('norma', width=270, anchor='w')
        table.column('p0', width=90, anchor='e')
        table.pack(fill='both', expand=True, pady=7)
        assignment = ttk.Frame(frame)
        assignment.pack(fill='x')
        ttk.Label(assignment, text='Fila normativa para el uso seleccionado').pack(side='left')
        def option_name(key, use):
            conditions = ', '.join(x for x in (f'pendiente {use.slope} %' if use.slope != '—' else '',
                                                f'cultivo {use.practice}' if use.practice != '—' else '') if x)
            return (f'{key[:5]} · {use.label}' + (f' · {conditions}' if conditions else '') +
                    f' · {use.values[0]}/{use.values[1]}/{use.values[2]}/{use.values[3]} mm')
        options_by_key = {key: option_name(key, use) for key, use in NORM_USES.items()}
        key_by_option = {label: key for key, label in options_by_key.items()}
        options = ['Sin equivalencia'] + list(options_by_key.values())
        search = tk.StringVar()
        ttk.Label(assignment, text='Buscar').pack(side='left', padx=(9, 3))
        ttk.Entry(assignment, textvariable=search, width=16).pack(side='left')
        selected_norm = tk.StringVar(value=options[0])
        norm_box = ttk.Combobox(assignment, textvariable=selected_norm, values=options,
                                state='readonly', width=58)
        norm_box.pack(side='left', padx=6)
        def filter_options(*_):
            needle = search.get().casefold().strip()
            norm_box['values'] = [value for value in options if needle in value.casefold()]
        search.trace_add('write', filter_options)
        mapping = {}
        current = {'summary': None}

        def refresh_threshold(*_):
            summary = current['summary']
            if summary is None:
                return
            areas = {entry['uso']: entry['m2'] for entry in summary['superficies']}
            result = threshold_summary(areas, group.get(), mapping)
            for item in table.get_children():
                table.delete(item)
            for entry in result['filas']:
                norm = NORM_USES.get(entry['fila_52ic'])
                display_norm = (f"{entry['fila_52ic'][:5]} · {norm.label}" if norm else 'Revisar')
                table.insert('', 'end', iid=entry['uso_siose'], values=(
                    entry['uso_siose'], f"{entry['area_m2']/10_000:.4f}",
                    display_norm,
                    entry['p0_inicial_mm'] if entry['p0_inicial_mm'] is not None else '—'))
            if result['p0_inicial_ponderado_mm'] is None:
                p0_label.set(f"Sin equivalencia: {result['area_sin_equivalencia_m2']/10_000:.4f} ha")
            else:
                p0_label.set(f"P₀ⁱ ponderado: {result['p0_inicial_ponderado_mm']:.3f} mm")
            target = Path(report_dir.get())
            target.mkdir(parents=True, exist_ok=True)
            (target/'umbrales_52ic.json').write_text(
                json.dumps({'tabla': '5.2-IC, tabla 2.3', 'fuente': source.get(),
                            'equivalencias': mapping, **result},
                           ensure_ascii=False, indent=2), encoding='utf-8')

        group.trace_add('write', refresh_threshold)

        def select_row(_):
            chosen = table.selection()
            if chosen:
                code = mapping.get(chosen[0])
                selected_norm.set(options_by_key.get(code, options[0]))
        table.bind('<<TreeviewSelect>>', select_row)

        def apply_assignment():
            chosen = table.selection()
            if not chosen:
                messagebox.showinfo('Selecciona un uso', 'Selecciona primero una fila de la tabla.', parent=window)
                return
            selected = selected_norm.get()
            if selected != options[0] and selected not in key_by_option:
                messagebox.showerror('Fila no válida', 'Selecciona una fila de la lista.', parent=window)
                return
            mapping[chosen[0]] = key_by_option.get(selected)
            refresh_threshold()
            table.selection_set(chosen[0])
        ttk.Button(assignment, text='Aplicar', command=apply_assignment).pack(side='left')

        def on_result(summary, saved):
            current['summary'] = summary
            mapping.clear()
            mapping.update({entry['uso']: DEFAULT_EQUIVALENCES.get(entry['uso'])
                            for entry in summary['superficies']})
            previous = Path(report_dir.get())/'umbrales_52ic.json'
            if previous.is_file():
                try:
                    old = json.loads(previous.read_text(encoding='utf-8'))
                    if old.get('fuente') == source.get():
                        mapping.update({name: code for name, code in old['equivalencias'].items()
                                        if name in mapping and (code is None or code in NORM_USES)})
                        group.set(old['grupo_suelo'])
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            refresh_threshold()
            status.set(f"{summary['poligonos_intersectados']} polígonos · "
                       f"{summary['usos_m2']/10_000:.4f} ha clasificados · "
                       f"cuenca vectorial {summary['cuenca_m2']/10_000:.4f} ha · "
                       f"diferencia {summary['desviacion_m2']/10_000:+.4f} ha. "
                       f"Guardado en {saved.name} y umbrales_52ic.json")
            run.configure(state='normal')

        def save_all():
            target = Path(report_dir.get())
            target.mkdir(parents=True, exist_ok=True)
            if current['summary'] is not None:
                save_landuse_summary(target, current['summary'], Path(source.get()))
                refresh_threshold()
            data = {'carpeta_informes': str(target), 'fuente_usos': source.get(),
                    'cv': cv.get(), 'grupo_suelo': group.get()}
            config.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
            status.set(f'Datos guardados en: {target}')

        def show_flows():
            dialog = tk.Toplevel(window)
            dialog.title('DRENIA · Parámetros y caudales racionales')
            dialog.geometry('780x690')
            outer = ttk.Frame(dialog, padding=14)
            outer.pack(fill='both', expand=True)
            ttk.Label(outer, text='Método racional · Cuenca menor de 50 km²',
                      font=('Segoe UI', 12, 'bold')).pack(anchor='w')
            ttk.Label(outer, text='DRENIA calcula L, J y Tc desde la cabecera hidrológica de toda la cuenca. Introduce βm regional y FT de cada periodo.',
                      wraplength=740).pack(anchor='w', pady=4)
            inputs = ttk.Frame(outer)
            inputs.pack(fill='x', pady=9)
            stored = Path(report_dir.get())/'parametros_caudales.json'
            try:
                initial = json.loads(stored.read_text(encoding='utf-8')) if stored.is_file() else {}
            except (OSError, ValueError):
                initial = {}
            variables = {}
            fields = [('lluvia_media_mm', 'Precipitación diaria media (mm)', ''),
                      ('beta_m', 'βm regional', ''),
                      ('i1_id', 'I₁/Id', '10'),
                      ('longitud_km', 'Recorrido hidráulico (km)', ''),
                      ('pendiente', 'Pendiente media recorrido (m/m)', ''),
                      ('tc_h', 'Tc directo (h; opcional)', '')]
            for index, (key, label, default) in enumerate(fields):
                ttk.Label(inputs, text=label).grid(row=index//2, column=(index%2)*2,
                                                    sticky='w', padx=(0, 5), pady=4)
                variable = tk.StringVar(value=initial.get(key, default))
                ttk.Entry(inputs, textvariable=variable, width=15).grid(
                    row=index//2, column=(index%2)*2+1, padx=(0, 25), pady=4)
                variables[key] = variable
            channel_row = ttk.Frame(outer)
            channel_row.pack(fill='x', pady=(0, 6))
            channel_button = ttk.Button(channel_row, text='Calcular cabecera hidrológica, L, J y Tc')
            channel_button.pack(side='left')
            channel_status = tk.StringVar(value='Longitud y pendiente editables; el trazado sigue todas las celdas D8 de la cuenca.')
            channel_state = {'metrics': None}
            ttk.Label(channel_row, textvariable=channel_status, wraplength=510).pack(side='left', padx=9)
            ttk.Label(outer, text='FT por periodo de retorno · deja vacíos los periodos aún sin dato').pack(anchor='w')
            periods = ttk.Frame(outer)
            periods.pack(fill='x', pady=6)
            ft = {}
            for i, period in enumerate(FLOW_PERIODS):
                ttk.Label(periods, text=f'T{period}').grid(row=i//4*2, column=i%4*2,
                                                           sticky='w', padx=5)
                v = tk.StringVar(value=initial.get('ft', {}).get(str(period), ''))
                ttk.Entry(periods, textvariable=v, width=11).grid(
                    row=i//4*2+1, column=i%4*2, padx=(5, 22))
                ft[period] = v
            info = tk.StringVar(value='Completa los parámetros; T5, T100 y T500 tienen prioridad.')
            ttk.Label(outer, textvariable=info, wraplength=730).pack(anchor='w', pady=6)
            outputs = ttk.Treeview(outer, columns=('t', 'pd', 'po', 'c', 'it', 'q'), show='headings')
            for key, heading, width in [('t', 'T (años)', 70), ('pd', 'Pd (mm)', 100),
                                        ('po', 'P₀ (mm)', 100), ('c', 'C', 90),
                                        ('it', 'I (mm/h)', 110), ('q', 'Q (m³/s)', 120)]:
                outputs.heading(key, text=heading)
                outputs.column(key, width=width, anchor='center')
            outputs.pack(fill='both', expand=True, pady=8)

            def collect():
                return {k: v.get().strip() for k, v in variables.items()} | {
                    'ft': {str(t): v.get().strip() for t, v in ft.items()}}

            def on_channel(result):
                channel_state['metrics'] = result
                variables['longitud_km'].set(f"{result['longitud_km']:.5f}")
                variables['pendiente'].set(f"{result['pendiente_m_m']:.7f}")
                variables['tc_h'].set('')
                tc = f"{result['tc_h']:.3f} h" if result['tc_h'] is not None else 'indeterminado (desnivel ≤ 0)'
                channel_status.set(f"Cabecera {result['cota_cabecera_m']:.2f} m · vertido "
                                   f"{result['cota_vertido_m']:.2f} m · L {result['longitud_km']:.3f} km · "
                                   f"J {result['pendiente_m_m']:.5f} · Tc {tc}")
                channel_button.configure(state='normal')
                store_inputs()

            def on_channel_error(detail):
                channel_button.configure(state='normal')
                channel_status.set('No se pudo trazar el recorrido: ' + detail)

            def start_channel():
                channel_button.configure(state='disabled')
                channel_status.set('Calculando el recorrido D8 más largo de toda la cuenca…')
                target = Path(report_dir.get())

                def worker():
                    try:
                        basin_result, work = open_saved_result(folder)
                        cache = target/'recorrido_hidrologico_metricas.json'
                        files = [folder/'cuenca_mascara.tif', work/'direccion_d8.tif',
                                 work/'acumulacion_celdas.tif', work/'mosaico.tif']
                        fingerprint = [(p.stat().st_size, p.stat().st_mtime_ns) for p in files]
                        for candidate in (cache, folder/'recorrido_hidrologico_metricas.json'):
                            if candidate.is_file():
                                stored_channel = json.loads(candidate.read_text(encoding='utf-8'))
                                if (stored_channel.get('metodo') == METHOD and
                                        stored_channel.get('punto_vertido') == basin_result['punto_ajustado'] and
                                        stored_channel.get('fuentes') == [list(x) for x in fingerprint]):
                                    self.events.put(('channel_ready', (dialog, on_channel, stored_channel)))
                                    return
                        channel = hydrological_path(folder/'cuenca_mascara.tif', work/'direccion_d8.tif',
                                                    work/'acumulacion_celdas.tif', work/'mosaico.tif',
                                                    tuple(basin_result['punto_ajustado']))
                        channel['punto_vertido'] = basin_result['punto_ajustado']
                        channel['fuentes'] = fingerprint
                        target.mkdir(parents=True, exist_ok=True)
                        save_channel(target, channel)
                        cache.write_text(json.dumps(channel, ensure_ascii=False, indent=2),
                                         encoding='utf-8')
                        self.events.put(('channel_ready', (dialog, on_channel, channel)))
                    except Exception as exc:
                        self.events.put(('channel_error', (dialog, on_channel_error, str(exc))))
                threading.Thread(target=worker, daemon=True).start()

            channel_button.configure(command=start_channel)

            def store_inputs():
                target = Path(report_dir.get())
                target.mkdir(parents=True, exist_ok=True)
                (target/'parametros_caudales.json').write_text(
                    json.dumps(collect(), ensure_ascii=False, indent=2), encoding='utf-8')
                save_all()
                info.set(f'Parámetros guardados en: {target}')

            def calculate_flows():
                try:
                    if current['summary'] is None:
                        raise ValueError('Calcula primero las superficies de usos.')
                    area_by_use = {item['uso']: item['m2'] for item in current['summary']['superficies']}
                    threshold = threshold_summary(area_by_use, group.get(), mapping)
                    if threshold['p0_inicial_ponderado_mm'] is None:
                        raise ValueError(f"Faltan equivalencias en {threshold['area_sin_equivalencia_m2']/10_000:.4f} ha.")
                    data = collect()
                    number = lambda value: float(value.replace(',', '.'))
                    tc = (number(data['tc_h']) if data['tc_h'] else
                          concentration_time(number(data['longitud_km']), number(data['pendiente'])))
                    result = rational_flows(
                        area_km2=json.loads((folder/'resultado.json').read_text(encoding='utf-8'))['area_km2'],
                        p0_initial=threshold['p0_inicial_ponderado_mm'],
                        cv=number(cv.get()), mean_daily_rain_mm=number(data['lluvia_media_mm']),
                        beta_m=number(data['beta_m']), torrentiality=number(data['i1_id']),
                        tc_hours=tc, ft=parse_ft(data['ft']))
                    for item in outputs.get_children():
                        outputs.delete(item)
                    for item in result['periodos']:
                        if item['estado'] == 'Calculado':
                            outputs.insert('', 'end', values=(item['periodo'], f"{item['pd_mm']:.3f}",
                                f"{item['p0_mm']:.3f}", f"{item['coeficiente_escorrentia']:.4f}",
                                f"{item['intensidad_mm_h']:.3f}", f"{item['caudal_m3_s']:.4f}"))
                        else:
                            outputs.insert('', 'end', values=(item['periodo'], '—', '—', '—', '—', 'Falta FT'))
                    target = Path(report_dir.get())
                    target.mkdir(parents=True, exist_ok=True)
                    (target/'caudales.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                    (target/'parametros_caudales.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                    save_all()
                    info.set(f"Tc {tc:.3f} h · KA {result['ka']:.4f} · Kt {result['kt']:.4f} · resultados: {target/'caudales.json'}")
                    return result, threshold, data
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    messagebox.showerror('Faltan datos para el caudal', str(exc), parent=dialog)

            def generate_excel():
                calculated = calculate_flows()
                if calculated is None:
                    return
                _, threshold, data = calculated
                chosen = filedialog.asksaveasfilename(
                    parent=dialog, title='Guardar Excel de caudales',
                    initialdir=report_dir.get(), initialfile='DRENIA_caudales.xlsx',
                    defaultextension='.xlsx', filetypes=[('Libro de Excel', '*.xlsx')])
                if not chosen:
                    return
                try:
                    path = write_excel_report(
                        Path(chosen), basin=json.loads((folder/'resultado.json').read_text(encoding='utf-8')),
                        landuse=current['summary'] | {'fuente': source.get()}, threshold=threshold,
                        inputs=data | {'cv': cv.get()}, channel=channel_state['metrics'])
                    info.set(f'Excel generado: {path}')
                    messagebox.showinfo('Excel generado', f'Libro guardado en:\n{path}', parent=dialog)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    messagebox.showerror('No se pudo generar el Excel', str(exc), parent=dialog)
            actions = ttk.Frame(outer)
            actions.pack(anchor='w')
            ttk.Button(actions, text='Guardar parámetros', command=store_inputs).pack(side='left')
            ttk.Button(actions, text='Calcular caudales', command=calculate_flows).pack(side='left', padx=8)
            ttk.Button(actions, text='Generar Excel…', command=generate_excel).pack(side='left', padx=8)
            start_channel()

        save_row = ttk.Frame(frame)
        save_row.pack(fill='x', pady=(5, 0))
        ttk.Button(save_row, text='Guardar', command=save_all).pack(side='left')
        ttk.Button(save_row, text='Parámetros y caudales…', command=show_flows).pack(side='left', padx=6)
        ttk.Button(save_row, text='Guardar en…', command=lambda: report_dir.set(
            filedialog.askdirectory(parent=window, title='Carpeta para informes y parámetros')
            or report_dir.get())).pack(side='left', padx=6)
        ttk.Label(save_row, textvariable=report_dir, wraplength=540).pack(side='left', padx=7)

        def calculate():
            path = Path(source.get())
            if not path.is_file():
                messagebox.showerror('Falta el GeoPackage', 'Selecciona un archivo .gpkg existente.', parent=window)
                return
            run.configure(state='disabled')
            status.set('Cortando los polígonos por la cuenca…')

            def worker():
                try:
                    summary = landuse_summary(folder/'cuenca.gpkg', path)
                    saved = save_landuse_summary(Path(report_dir.get()), summary, path)
                    self.events.put(('landuse_done', (window, on_result, summary, saved)))
                except Exception as exc:
                    self.events.put(('landuse_error', (window, run, status, str(exc))))
            threading.Thread(target=worker, daemon=True).start()
        run.configure(command=calculate)
        prior = Path(report_dir.get())/'superficies_usos.json'
        if prior.is_file():
            try:
                prior_data = json.loads(prior.read_text(encoding='utf-8'))
                if not source.get():
                    source.set(prior_data.get('fuente', ''))
                on_result(prior_data, prior)
            except (OSError, ValueError, KeyError, TypeError):
                pass

    def restore_saved_result(self, destination: Path):
        result, work = open_saved_result(destination)
        point = tuple(result['punto_inicial'])
        if len(point) != 2:
            raise ValueError('El punto guardado no contiene dos coordenadas.')
        seed = Path(result.get('tesela_inicial', ''))
        candidates = [Path(result['carpeta_mdt'])] if result.get('carpeta_mdt') else []
        used = [Path(p) for p in result['teselas']]
        if not seed.is_file():
            seed = next((p for p in used if p.is_file() and
                         self._point_in_tile(p, point)), Path())
        if seed.is_file():
            candidates.insert(0, seed.parent)
        elif used:
            candidates.append(used[0].parent)
        source = next((p for p in candidates if p.is_dir()), None)
        if source is None:
            source = filedialog.askdirectory(title='Localiza la carpeta de MDT para continuar')
        if source:
            self.folder.set(str(source))
            self.tiles, errors = index_tiles(Path(source))
            self.tile_box['values'] = [str(t.path.relative_to(source)) for t in self.tiles]
            matches = [i for i, tile in enumerate(self.tiles)
                       if tile.bounds[0] <= point[0] < tile.bounds[2]
                       and tile.bounds[1] < point[1] <= tile.bounds[3]]
            if matches:
                self.tile_box.current(matches[0])
                self.load_preview()
                seed = self.tiles[matches[0]].path
            else:
                self.tile_box.set('')
                self.tiles = []
            for error in errors[:5]:
                self._log('Se omite ' + error)
        else:
            self.tiles = []
            self.tile_box['values'] = []
            self.tile_box.set('')
        self.output.set(str(destination))
        self.radius.set(str(result['radio_ajuste_m']))
        self.breach.set(str(result['busqueda_brecha_celdas']))
        self.outlet = point
        self.x_coord.set(f'{point[0]:.2f}')
        self.y_coord.set(f'{point[1]:.2f}')
        self.result_outlet = tuple(result['punto_ajustado'])
        self.point_label.configure(text=f'X {point[0]:.2f} · Y {point[1]:.2f}\nPunto ajustado: '
                                        f'{self.result_outlet[0]:.2f}, {self.result_outlet[1]:.2f}')
        self.load_result_preview(destination, work)
        self.accum_path = work/'acumulacion_celdas.tif'
        self.hydro_folder = work
        self.diagnostic_generation += 1
        self.diagnostic_images.clear()
        self.select_view()
        self.refresh_stream_overlay()
        self.last_run = ({'result': result, 'destination': destination,
                          'seed': seed, 'point': point, 'radius': float(result['radio_ajuste_m']),
                          'breach': int(result['busqueda_brecha_celdas'])}
                         if self.tiles else None)
        self.audit_candidates = []
        self.audit_box['values'] = []
        self.audit_button.configure(state='disabled')
        if self.last_run:
            self.update_audit_options()
        self.status.set(f'Análisis recuperado · {result["area_km2"]:.4f} km²')
        self._load_channel(destination, result)
        if not self.tiles:
            self._log('Análisis recuperado. Para recalcular o auditar, vuelve a seleccionar la carpeta de MDT.')
        self.draw()

    @staticmethod
    def _point_in_tile(path, point):
        try:
            with rasterio.open(path) as ds:
                b = ds.bounds
                return b.left <= point[0] < b.right and b.bottom < point[1] <= b.top
        except (OSError, rasterio.errors.RasterioError):
            return False

    def pick_binary(self):
        path = filedialog.askopenfilename(title='Ejecutable whitebox_tools')
        if path: self.binary.set(path)

    def choose_pnoa(self):
        self.ortho_source = 'PNOA'
        self.request_ortho()

    def choose_local_ortho(self):
        path = filedialog.askopenfilename(title='Ortofoto georreferenciada',
                                          filetypes=[('GeoTIFF RGB', '*.tif *.tiff')])
        if path:
            self.ortho_source = Path(path)
            self.request_ortho()

    def request_ortho(self):
        if not self.preview or not self.preview_bounds or not self.current_crs: return
        self.ortho_generation += 1
        generation = self.ortho_generation
        self.ortho_preview = None
        self.draw()
        bounds, crs, width, height = (self.preview_bounds, self.current_crs,
                                      self.preview.width, self.preview.height)
        source = self.ortho_source
        self._log('Cargando ortofoto ' + ('PNOA…' if source == 'PNOA' else str(source)))
        def worker():
            try:
                if source == 'PNOA':
                    image = pnoa_image(bounds, crs, width, height)
                else:
                    image = local_ortho_image(source, bounds, crs, width, height)
                self.events.put(('ortho_ready', (generation, image)))
            except Exception as exc:
                self.events.put(('ortho_error', (generation, str(exc))))
        threading.Thread(target=worker, daemon=True).start()

    def load_preview(self):
        if not self.tiles or self.tile_box.current() < 0: return
        tile = self.tiles[self.tile_box.current()]
        try:
            with rasterio.open(tile.path) as ds:
                factor = max(ds.width / 1200, ds.height / 1200, 1)
                height, width = max(1, round(ds.height/factor)), max(1, round(ds.width/factor))
                arr = ds.read(1, out_shape=(height, width), resampling=Resampling.average, masked=True)
                valid = arr.compressed()
                if len(valid) == 0: raise ValueError('El MDT no contiene valores válidos.')
                low, high = np.percentile(valid, [2, 98])
                grey = np.clip((arr.filled(low)-low) / max(high-low, 1e-6)*255, 0, 255).astype('uint8')
                grey[np.ma.getmaskarray(arr)] = 230
            self.preview = Image.fromarray(grey, 'L').convert('RGB')
            self.preview_bounds = tuple(tile.bounds)
            self.current_crs = tile.crs
            self.overlay = None
            self.stream_overlay = None
            self.accum_path = None
            self.last_run = None
            self.channel_generation += 1
            self.channel_head = None
            self.channel_route = None
            self.channel_summary.set('Cabecera hidrológica: disponible después de delimitar la cuenca.')
            self.audit_candidates = []
            self.hydro_folder = None
            self.diagnostic_images = {}
            self.diagnostic_generation += 1
            self.view_mode.set('MDT')
            self.view_note.configure(text='Altitud (m)')
            self.audit_box['values'] = []
            self.audit_button.configure(state='disabled')
            self.outlet = self.result_outlet = None
            self.x_coord.set('')
            self.y_coord.set('')
            self.zoom = 1
            self.pan_x = self.pan_y = 0
            self.point_label.configure(text='Sin seleccionar')
            self.status.set(f'{tile.path.name} · {tile.resolution[0]:g} × {tile.resolution[1]:g} m · {tile.crs}')
            self.draw()
            self.request_ortho()
        except Exception as exc:
            messagebox.showerror('No se pudo abrir el MDT', str(exc))

    def load_result_preview(self, destination: Path, final_directory: Path):
        mosaic = Path(final_directory) / 'mosaico.tif'
        with rasterio.open(mosaic) as ds:
            factor = max(ds.width / 1200, ds.height / 1200, 1)
            height, width = max(1, round(ds.height/factor)), max(1, round(ds.width/factor))
            arr = ds.read(1, out_shape=(height, width),
                          resampling=Resampling.average, masked=True)
            valid = arr.compressed()
            low, high = np.percentile(valid, [2, 98])
            grey = np.clip((arr.filled(low)-low)/max(high-low, 1e-6)*255, 0, 255).astype('uint8')
            grey[np.ma.getmaskarray(arr)] = 230
            self.preview = Image.fromarray(grey, 'L').convert('RGB')
            self.preview_bounds = tuple(ds.bounds)
            self.current_crs = ds.crs.to_string()
        with rasterio.open(destination/'cuenca_mascara.tif') as src:
            mask = src.read(1, out_shape=(height, width), resampling=Resampling.nearest)
        color = np.zeros((height, width, 4), dtype='uint8')
        color[mask == 1] = (0, 218, 190, 118)
        self.overlay = Image.fromarray(color, 'RGBA')
        self.stream_overlay = None
        self.zoom = 1
        self.pan_x = self.pan_y = 0
        self.request_ortho()

    def _layout_image(self):
        cw, ch = max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)
        if self.preview is None: return None
        w, h = self.preview.size
        scale = min(cw/w, ch/h) * self.zoom
        return (cw-w*scale)/2+self.pan_x, (ch-h*scale)/2+self.pan_y, scale

    def select_view(self):
        mode = self.view_mode.get()
        self.view_note.configure(text={
            'MDT': 'Altitud (m)',
            'Dirección D8': 'Color = vecino receptor; Whitebox D8: NE 1 · E 2 · SE 4 · S 8 · SO 16 · O 32 · NO 64 · N 128',
            'Acumulación': 'Color claro = mayor número de celdas aguas arriba (escala logarítmica)',
        }[mode])
        if mode != 'MDT' and mode not in self.diagnostic_images:
            if not self.hydro_folder or not self.preview:
                self._log('Calcula primero los cauces para consultar esta vista.')
            else:
                name = 'direccion_d8.tif' if mode == 'Dirección D8' else 'acumulacion_celdas.tif'
                path = self.hydro_folder/name
                if path.is_file():
                    generation = self.diagnostic_generation
                    size = self.preview.size
                    def worker():
                        try:
                            image = diagnostic_preview(path, 'direction' if mode == 'Dirección D8'
                                                       else 'accumulation', *size)
                            self.events.put(('diagnostic_ready', (generation, mode, image)))
                        except Exception as exc:
                            self.events.put(('diagnostic_error', str(exc)))
                    threading.Thread(target=worker, daemon=True).start()
        self.draw()

    def draw(self):
        self.canvas.delete('all')
        layout = self._layout_image()
        if not layout:
            self.canvas.create_text(200, 160, text='Selecciona una carpeta y un MDT', fill='#5b6b76')
            return
        x0, y0, scale = layout
        mode = self.view_mode.get()
        diagnostic = self.diagnostic_images.get(mode)
        image = (diagnostic or self.preview).copy()
        if mode == 'MDT' and self.ortho_preview is not None and self.ortho_preview.size == image.size:
            image = Image.blend(self.ortho_preview, image, self.transparency.get()/100)
        if mode == 'MDT' and self.stream_overlay is not None and self.stream_overlay.size == image.size:
            image = Image.alpha_composite(image.convert('RGBA'), self.stream_overlay).convert('RGB')
        if self.overlay is not None and self.overlay.size == image.size:
            image = Image.alpha_composite(image.convert('RGBA'), self.overlay).convert('RGB')
        if self.channel_route and self.preview_bounds:
            left, bottom, right, top = self.preview_bounds
            pixels = [((x-left)/(right-left)*image.width, (top-y)/(top-bottom)*image.height)
                      for x, y in self.channel_route]
            ImageDraw.Draw(image).line(pixels, fill='#ff6138', width=3, joint='curve')
        self.image_ref = ImageTk.PhotoImage(image.resize(
            (max(1, round(image.width*scale)), max(1, round(image.height*scale))),
            Image.Resampling.BILINEAR))
        self.canvas.create_image(x0, y0, image=self.image_ref, anchor='nw')
        for position, color, label in ((self.outlet, '#fbc02d', 'Punto elegido'),
                                       (self.result_outlet, '#00dfd4', 'Ajustado'),
                                       (self.channel_head, '#ff6b39', 'Cabecera hidrológica')):
            if position:
                left, bottom, right, top = self.preview_bounds
                if not (left <= position[0] <= right and bottom <= position[1] <= top):
                    continue
                px = x0 + (position[0]-left)/(right-left)*image.width*scale
                py = y0 + (top-position[1])/(top-bottom)*image.height*scale
                self.canvas.create_oval(px-6, py-6, px+6, py+6, fill=color,
                                        outline='#222', width=2)
                self.canvas.create_text(px+9, py-12, anchor='w', text=label, fill='#111')

    def change_zoom(self, mult, x, y):
        if self.preview is None: return
        new_zoom = max(1, min(20, self.zoom*mult))
        ratio = new_zoom/self.zoom
        self.zoom = new_zoom
        self.pan_x = ratio*self.pan_x + (1-ratio)*(x-self.canvas.winfo_width()/2)
        self.pan_y = ratio*self.pan_y + (1-ratio)*(y-self.canvas.winfo_height()/2)
        self.draw()

    def wheel(self, e): self.change_zoom(1.2 if e.delta > 0 else 1/1.2, e.x, e.y)
    def press(self, e): self.drag_start = (e.x, e.y, False)
    def drag(self, e):
        if self.drag_start:
            x, y, _ = self.drag_start
            self.pan_x += e.x-x
            self.pan_y += e.y-y
            self.drag_start = (e.x, e.y, True)
            self.draw()

    def release(self, e):
        if not self.drag_start: return
        dragged = self.drag_start[2]
        self.drag_start = None
        if dragged or not self.preview: return
        x0, y0, scale = self._layout_image()
        px, py = (e.x-x0)/scale, (e.y-y0)/scale
        if not (0 <= px < self.preview.width and 0 <= py < self.preview.height): return
        left, bottom, right, top = self.preview_bounds
        self.set_point((left + px/self.preview.width*(right-left),
                        top - py/self.preview.height*(top-bottom)))

    def set_point(self, point):
        if self.outlet != point:
            self.channel_generation += 1
            self.channel_head = None
            self.channel_route = None
            self.channel_summary.set('Cabecera hidrológica: disponible después de delimitar la cuenca.')
        self.outlet = point
        self.x_coord.set(f'{point[0]:.2f}')
        self.y_coord.set(f'{point[1]:.2f}')
        self.result_outlet = None
        self.overlay = None
        info = f'X {point[0]:.2f} · Y {point[1]:.2f}'
        if self.accum_path:
            try:
                radius = float(self.radius.get().replace(',', '.'))
                threshold = float(self.threshold.get().replace(',', '.'))
                snapped, cells, _ = snap_to_stream(self.accum_path, point, radius, threshold)
                self.result_outlet = snapped
                pixel_area = self.tiles[self.tile_box.current()].resolution
                area = cells*pixel_area[0]*pixel_area[1]/1_000_000
                info += f'\nAjuste {math.dist(point, snapped):.1f} m · aporte previo {area:.4f} km²'
            except (ValueError, OSError) as exc:
                info += '\nSin ajuste: ' + str(exc)
        self.point_label.configure(text=info)
        self.draw()

    def go_coordinates(self):
        try:
            point = (float(self.x_coord.get().replace(',', '.')),
                     float(self.y_coord.get().replace(',', '.')))
        except ValueError:
            messagebox.showerror('Coordenadas', 'Introduce X e Y numéricas en el CRS del MDT.')
            return
        matches = [i for i, tile in enumerate(self.tiles) if tile.bounds[0] <= point[0] < tile.bounds[2]
                   and tile.bounds[1] < point[1] <= tile.bounds[3]]
        if not matches:
            messagebox.showerror('Coordenadas', 'Ese punto no está dentro de ninguna tesela indexada.')
            return
        if matches[0] != self.tile_box.current():
            self.tile_box.current(matches[0])
            self.load_preview()
        self.set_point(point)

    def refresh_stream_overlay(self):
        if not self.accum_path or not self.preview:
            self._log('Calcula primero los cauces de la tesela seleccionada.')
            return
        try:
            threshold = float(self.threshold.get().replace(',', '.'))
            if threshold <= 0: raise ValueError('El área mínima debe ser positiva.')
            with rasterio.open(self.accum_path) as ds:
                h, w = self.preview.height, self.preview.width
                cells = threshold*1_000_000/abs(ds.transform.a*ds.transform.e)
                transform = ds.transform * rasterio.Affine.scale(ds.width/w, ds.height/h)
                with WarpedVRT(ds, crs=ds.crs, transform=transform, width=w,
                               height=h, resampling=Resampling.max) as reduced:
                    data = reduced.read(1, masked=True)
                network = (data.data >= cells) & (~np.ma.getmaskarray(data))
            alpha = network.astype('uint8')*205
            color = np.zeros((h, w, 4), dtype='uint8')
            color[:, :, 0] = 0
            color[:, :, 1] = 229
            color[:, :, 2] = 255
            color[:, :, 3] = alpha
            self.stream_overlay = Image.fromarray(color, 'RGBA')
            self.draw()
            self._log(f'Cauces visibles: umbral {threshold:g} km². Aporte preliminar limitado a la tesela inicial.')
            if self.outlet and self.overlay is None: self.set_point(self.outlet)
            if not np.any(network):
                self._log('No aparecen cauces: reduce el área mínima drenada y pulsa Actualizar.')
        except (ValueError, OSError) as exc:
            messagebox.showerror('Umbral de cauces', str(exc))

    def prepare(self):
        if self.busy or self.tile_box.current() < 0: return
        if not self.output.get():
            self.pick_output()
            if not self.output.get(): return
        try:
            exe = locate_whitebox(self.binary.get() or None)
            breach = int(self.breach.get())
            if breach < 1: raise ValueError('La búsqueda de brecha debe ser positiva.')
        except (ValueError, FileNotFoundError) as exc:
            messagebox.showerror('Parámetros', str(exc))
            return
        self.busy = True
        self._start_clock('Calculando cauces')
        self.calculate.configure(state='disabled')
        self.network_button.configure(state='disabled')
        self.audit_button.configure(state='disabled')
        self.tile_box.configure(state='disabled')
        self.status.set('Calculando dirección y acumulación de flujo…')
        tile = self.tiles[self.tile_box.current()]
        destination = Path(self.output.get())
        def worker():
            try:
                path = prepare_hydrology(tile, destination, exe, breach,
                                         log=lambda line: self.events.put(('log', line)))
                self.events.put(('network_ready', path))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def start(self):
        if self.busy: return
        if self.accum_path and self.outlet:
            self.set_point(self.outlet)
        if not self.outlet or self.tile_box.current() < 0:
            messagebox.showwarning('Falta el punto', 'Selecciona una tesela y haz clic en el punto de vertido.')
            return
        if self.accum_path and not self.result_outlet:
            messagebox.showwarning('Punto fuera del cauce',
                                   'Elige un cauce azul próximo o modifica el radio y vuelve a señalar el punto.')
            return
        if not self.output.get():
            self.pick_output()
            if not self.output.get(): return
        try:
            radius, breach = float(self.radius.get().replace(',', '.')), int(self.breach.get())
            exe = locate_whitebox(self.binary.get() or None)
            if radius < 0 or breach < 1: raise ValueError('Parámetros fuera de rango')
        except (ValueError, FileNotFoundError) as exc:
            messagebox.showerror('Parámetros', str(exc))
            return
        self.busy = True
        self._start_clock('Preparando el MDT')
        self.calculate.configure(state='disabled')
        self.network_button.configure(state='disabled')
        self.audit_button.configure(state='disabled')
        self.tile_box.configure(state='disabled')
        self.status.set('Estamos rellenando la cuenca… Sigue el avance y el cronómetro debajo.')
        point, confirmed = self.outlet, self.result_outlet
        destination = Path(self.output.get())
        candidates = [tile for tile in self.tiles if tile.bounds[0] <= point[0] < tile.bounds[2]
                      and tile.bounds[1] < point[1] <= tile.bounds[3]]
        if not candidates:
            self.busy = False
            self._stop_clock()
            self.calculate.configure(state='normal')
            self.network_button.configure(state='normal')
            self.tile_box.configure(state='readonly')
            messagebox.showerror('Punto fuera del MDT', 'El punto no coincide con una tesela indexada.')
            return
        tile = candidates[0]
        def worker():
            try:
                result = delineate(self.tiles, tile.path, point, destination, exe, radius,
                                   breach, log=lambda line: self.events.put(('log', line)),
                                   fixed_point=confirmed)
                self.events.put(('done', (result, destination, tile.path, point, radius, breach)))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def update_audit_options(self):
        if not self.last_run:
            return
        selected = {Path(path) for path in self.last_run['result']['teselas']}
        if not selected.issubset({t.path for t in self.tiles}):
            self.audit_candidates = []
            self.audit_box['values'] = []
            self.audit_button.configure(state='disabled')
            self._log('Para auditar, selecciona la carpeta original de MDT con todas las teselas utilizadas.')
            return
        self.audit_candidates = neighboring_tiles(self.tiles, selected)
        choices = ([f'Todas las teselas vecinas ({len(self.audit_candidates)})'] +
                   [t.path.name for t in self.audit_candidates]) if self.audit_candidates else []
        self.audit_box['values'] = choices
        if self.audit_candidates:
            self.audit_box.current(1)  # A single tile is the low-cost default.
            self.audit_button.configure(state='normal')
            self._log(f'{len(self.audit_candidates)} teselas vecinas sin analizar. Puedes auditar una o todas.')
        else:
            self.audit_selection.set('Sin teselas vecinas pendientes')
            self.audit_button.configure(state='disabled')

    def audit(self):
        if self.busy or not self.last_run or not self.audit_candidates: return
        index = self.audit_box.current()
        if index < 0: return
        chosen = self.audit_candidates if index == 0 else [self.audit_candidates[index-1]]
        info = self.last_run
        original = info['result']
        seed, point = info['seed'], info['point']
        fixed = tuple(original['punto_ajustado'])
        forced = sorted(({Path(p) for p in original['teselas']} - {seed}) |
                        {t.path for t in chosen})
        suffix = 'todas' if index == 0 else re.sub(r'[^a-zA-Z0-9_-]', '_', chosen[0].path.stem)
        destination = info['destination']/('auditoria_'+suffix)
        try:
            exe = locate_whitebox(self.binary.get() or None)
        except FileNotFoundError as exc:
            messagebox.showerror('Motor', str(exc))
            return
        self.busy = True
        self.calculate.configure(state='disabled')
        self.network_button.configure(state='disabled')
        self.audit_button.configure(state='disabled')
        self.tile_box.configure(state='disabled')
        self.status.set('Auditando ' + ', '.join(t.path.name for t in chosen) + '…')
        def worker():
            try:
                audit_result = delineate(self.tiles, seed, point, destination, exe,
                                         info['radius'], info['breach'],
                                         log=lambda line: self.events.put(('log', line)),
                                         fixed_point=fixed, forced_tiles=forced)
                report = compare_basins(info['destination']/'cuenca_mascara.tif',
                                        destination/'cuenca_mascara.tif',
                                        destination/'diferencias_auditoria.tif')
                report['teselas_agregadas_para_auditoria'] = [str(t.path) for t in chosen]
                (destination/'comparacion.json').write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                self.events.put(('audit_done', (report, destination, audit_result)))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'log':
                    self._log(value)
                    if self.started_at is not None:
                        self.last_activity = time.monotonic()
                        if value.startswith('Analizando: '):
                            self.phase = value.replace('Analizando: ', '', 1)
                        elif value.startswith('Teselas: '):
                            self.phase = 'Preparando teselas'
                        elif value.startswith('La cuenca alcanza el borde: '):
                            self.phase = 'Ampliando la cuenca con más teselas'
                        elif value.startswith('Punto ajustado a '):
                            self.phase = 'Delimitando la cuenca'
                elif kind == 'ortho_ready':
                    generation, picture = value
                    if generation == self.ortho_generation:
                        self.ortho_preview = picture
                        self.draw()
                        self._log('Ortofoto cargada. Transparencia 0% = ortofoto visible.')
                elif kind == 'ortho_error':
                    generation, detail = value
                    if generation == self.ortho_generation:
                        self._log('No se pudo cargar la ortofoto: ' + detail)
                elif kind == 'diagnostic_ready':
                    generation, mode, picture = value
                    if generation == self.diagnostic_generation:
                        self.diagnostic_images[mode] = picture
                        if self.view_mode.get() == mode: self.draw()
                elif kind == 'diagnostic_error':
                    self._log('No se pudo mostrar el ráster hidrológico: ' + value)
                elif kind == 'landuse_done':
                    window, on_result, summary, saved = value
                    if window.winfo_exists():
                        on_result(summary, saved)
                elif kind == 'landuse_error':
                    window, button, status, detail = value
                    if window.winfo_exists():
                        status.set('No se pudieron calcular las superficies.')
                        button.configure(state='normal')
                        messagebox.showerror('Superficies de usos', detail, parent=window)
                elif kind == 'channel_ready':
                    dialog, callback, metrics = value
                    if dialog.winfo_exists():
                        callback(metrics)
                elif kind == 'channel_error':
                    dialog, callback, detail = value
                    if dialog.winfo_exists():
                        callback(detail)
                elif kind == 'main_channel_ready':
                    generation, metrics = value
                    if generation == self.channel_generation:
                        self.channel_head = (metrics['cabecera_x'], metrics['cabecera_y'])
                        self.channel_route = metrics['geometry']['coordinates']
                        tc = f"{metrics['tc_h']:.3f} h" if metrics['tc_h'] is not None else 'indeterminado'
                        self.channel_summary.set(
                            f"Cabecera hidrológica: X {metrics['cabecera_x']:.2f}, Y {metrics['cabecera_y']:.2f} "
                            f"· cota {metrics['cota_cabecera_m']:.2f} m\n"
                            f"Vertido: cota {metrics['cota_vertido_m']:.2f} m · desnivel {metrics['desnivel_m']:.2f} m\n"
                            f"Recorrido D8: {metrics['longitud_km']:.3f} km · pendiente {metrics['pendiente_m_m']:.5f} "
                            f"· Tc {tc}")
                        self.draw()
                elif kind == 'main_channel_error':
                    generation, detail = value
                    if generation == self.channel_generation:
                        self.channel_summary.set('No se pudo determinar la cabecera: ' + detail)
                        self._log('Cauce principal: ' + detail)
                elif kind == 'error':
                    self.busy = False
                    self._stop_clock()
                    self.calculate.configure(state='normal')
                    self.network_button.configure(state='normal')
                    self.tile_box.configure(state='readonly')
                    if self.last_run and self.audit_candidates:
                        self.audit_button.configure(state='normal')
                    self.status.set('No se pudo completar el cálculo.')
                    messagebox.showerror('Error de cálculo', value)
                elif kind == 'network_ready':
                    self.busy = False
                    self._stop_clock()
                    self.calculate.configure(state='normal')
                    self.network_button.configure(state='normal')
                    self.tile_box.configure(state='readonly')
                    self.accum_path = value
                    self.hydro_folder = Path(value).parent
                    self.diagnostic_generation += 1
                    self.diagnostic_images.clear()
                    self.select_view()
                    self.refresh_stream_overlay()
                    if self.outlet: self.set_point(self.outlet)
                    self.status.set('Cauces calculados. Elige el vertido sobre una línea azul.')
                elif kind == 'done':
                    self.busy = False
                    self._stop_clock()
                    self.calculate.configure(state='normal')
                    self.network_button.configure(state='normal')
                    self.tile_box.configure(state='readonly')
                    result, destination, seed, point, radius, breach = value
                    self.last_run = {'result': result, 'destination': destination,
                                     'seed': seed, 'point': point, 'radius': radius,
                                     'breach': breach}
                    self.result_outlet = tuple(result['punto_ajustado'])
                    try:
                        self.load_result_preview(destination, Path(result['directorio_final']))
                        self.accum_path = Path(result['directorio_final'])/'acumulacion_celdas.tif'
                        self.hydro_folder = Path(result['directorio_final'])
                        self.diagnostic_generation += 1
                        self.diagnostic_images.clear()
                        self.select_view()
                        self.refresh_stream_overlay()
                    except Exception as exc:
                        self._log('No se pudo mostrar la máscara en el visor: ' + str(exc))
                    self.status.set(f'Área: {result["area_km2"]:.4f} km² · '
                                    + ('sin borde detectado' if result['resultado_completo'] else 'borde sin cobertura'))
                    self.update_audit_options()
                    self._load_channel(destination, result)
                    self.draw()
                    messagebox.showinfo('Cuenca delimitada',
                        f'Área: {result["area_km2"]:.4f} km²\n'
                        f'Teselas usadas: {len(result["teselas"])}\n'
                        f'Cobertura: {"sin corte detectado" if result["resultado_completo"] else "faltan datos en un borde"}\n'
                        f'Vecinas aún sin analizar: {len(self.audit_candidates)}\n\n'
                        f'Resultados: {destination}')
                elif kind == 'audit_done':
                    self.busy = False
                    self._stop_clock()
                    self.calculate.configure(state='normal')
                    self.network_button.configure(state='normal')
                    self.audit_button.configure(state='normal')
                    self.tile_box.configure(state='readonly')
                    report, destination, audit_result = value
                    message = (f'Original: {report["area_original_km2"]:.4f} km²\n'
                               f'Con tesela adicional: {report["area_auditoria_km2"]:.4f} km²\n'
                               f'Solo en la original: {report["solo_original_km2"]:.4f} km²\n'
                               f'Solo en la auditoría: {report["solo_auditoria_km2"]:.4f} km²\n'
                               f'Coincidencia espacial: {report["coincidencia_porcentaje"]:.2f}%\n\n'
                               f'Diferencias y nueva cuenca: {destination}')
                    self._log(message.replace('\n', ' | '))
                    self.status.set('Auditoría completada. Consulta diferencias_auditoria.tif.')
                    messagebox.showinfo('Comparación de teselas', message)
        except queue.Empty: pass
        self._update_clock()
        self.after(120, self._poll)


if __name__ == '__main__':
    Window().mainloop()
