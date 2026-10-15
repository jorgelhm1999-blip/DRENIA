"""Editable Excel report following DRENIA's three-panel hydrology mockup."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.workbook.properties import CalcProperties

from flow import FLOW_PERIODS
from landuse import _YT_ROWS
from norm52 import NORM_USES

NAVY = '172C40'
TEAL = '087F84'
BLUE = '216D83'
ORANGE = 'B95B35'
PALE = 'E8F5F3'
PAPER = 'F4F7F9'
INPUT = 'E7F0FF'
GRAY = '617486'
WHITE = 'FFFFFF'


def _number(value):
    return float(str(value).replace(',', '.'))


def _band(sheet, row, title, last='K'):
    sheet.merge_cells(f'A{row}:{last}{row}')
    cell = sheet.cell(row, 1, title)
    cell.fill = PatternFill('solid', fgColor=WHITE)
    cell.font = Font(name='Aptos', size=11, bold=True, color=NAVY)
    cell.alignment = Alignment(vertical='center', indent=1)
    sheet.row_dimensions[row].height = 30
    for cells in sheet.iter_rows(min_row=row, max_row=row, min_col=1, max_col=11):
        for item in cells:
            item.border = Border(bottom=Side(style='thin', color='CBD9DF'))


def _table_header(sheet, row, labels):
    for col, label in enumerate(labels, 1):
        cell = sheet.cell(row, col, label)
        cell.fill = PatternFill('solid', fgColor=NAVY)
        cell.font = Font(name='Aptos', size=10, bold=True, color=WHITE)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    sheet.row_dimensions[row].height = 34


def _banner(sheet, subtitle):
    sheet.merge_cells('A1:K3')
    cell = sheet['A1']
    cell.value = 'DRENIA   |   Informe de cálculo hidrológico'
    cell.fill = PatternFill('solid', fgColor=NAVY)
    cell.font = Font(name='Aptos Display', size=20, bold=True, color=WHITE)
    cell.alignment = Alignment(vertical='center', indent=1)
    for row in (1, 2, 3):
        sheet.row_dimensions[row].height = 20
    sheet.merge_cells('A4:K4')
    sheet['A4'] = subtitle
    sheet['A4'].font = Font(name='Aptos', size=10, color=GRAY)
    sheet['A4'].alignment = Alignment(indent=1, vertical='center')
    sheet.row_dimensions[4].height = 26


def _card(sheet, left, right, label, formula, color):
    sheet.merge_cells(start_row=6, start_column=left, end_row=6, end_column=right)
    sheet.merge_cells(start_row=7, start_column=left, end_row=9, end_column=right)
    title = sheet.cell(6, left, label)
    title.font = Font(name='Aptos', size=10, bold=True, color=GRAY)
    title.alignment = Alignment(indent=1, vertical='center')
    value = sheet.cell(7, left, formula)
    value.font = Font(name='Aptos Display', size=18, bold=True, color=color)
    value.alignment = Alignment(indent=1, vertical='center')
    value.number_format = '0.000 "m³/s"'
    for row in range(6, 10):
        for col in range(left, right+1):
            cell = sheet.cell(row, col)
            cell.fill = PatternFill('solid', fgColor=WHITE)
            cell.border = Border(left=Side(style='medium', color=color) if col == left else Side(),
                                 bottom=Side(style='hair', color='DDE6EB') if row == 9 else Side())


def export_excel(path: Path, *, basin: dict, landuse: dict, threshold: dict,
                 inputs: dict, channel: dict | None = None) -> Path:
    """Export live formulas for all periods, inputs, land-use thresholds and YT."""
    if threshold['p0_inicial_ponderado_mm'] is None or not threshold['filas']:
        raise ValueError('Revisa las superficies y equivalencias antes de exportar el Excel.')
    path = Path(path)
    wb = Workbook()
    wb.calculation = CalcProperties(calcMode='auto', fullCalcOnLoad=True, forceFullCalc=True)
    main = wb.active
    main.title = '01 Resumen'
    uses = wb.create_sheet('02 Usos SIOSE')
    source = wb.create_sheet('03 Fuentes y control')
    main.sheet_properties.tabColor = TEAL
    uses.sheet_properties.tabColor = BLUE
    source.sheet_properties.tabColor = GRAY

    # Surface breakdown, traceable to each selected 5.2-IC row.
    _banner(uses, 'Usos SIOSE recortados a la cuenca | grupo hidrológico ' + threshold['grupo_suelo'])
    _band(uses, 6, '01  SUPERFICIES Y EQUIVALENCIAS')
    _table_header(uses, 8, ['Uso SIOSE', 'Código 5.2-IC', 'Categoría normativa', 'Área (m²)',
                            'Área (ha)', 'P₀ⁱ (mm)', 'Área × P₀ⁱ', 'Grupo', 'Pendiente',
                            'Práctica', '% de área'])
    for row, entry in enumerate(threshold['filas'], 9):
        code = entry['fila_52ic']
        norm = NORM_USES.get(code)
        fields = [entry['uso_siose'], code, norm.label if norm else 'Sin equivalencia',
                  entry['area_m2'], f'=D{row}/10000', entry['p0_inicial_mm'],
                  f'=D{row}*F{row}', threshold['grupo_suelo'],
                  norm.slope if norm else '', norm.practice if norm else '', None]
        for col, value in enumerate(fields, 1):
            cell = uses.cell(row, col, value)
            cell.font = Font(name='Aptos', size=10, color=NAVY)
            cell.alignment = Alignment(vertical='center', indent=1 if col in (1, 2, 3, 8, 9, 10) else 0,
                                       horizontal='left' if col in (1, 2, 3, 8, 9, 10) else 'right')
            if row % 2 == 0:
                cell.fill = PatternFill('solid', fgColor=PAPER)
        uses.cell(row, 11, f'=IFERROR(D{row}/D{9+len(threshold["filas"])},0)')
        uses.cell(row, 11).number_format = '0.00%'
        for col in (4, 5, 6, 7):
            uses.cell(row, col).number_format = '#,##0.000'
    total = 9 + len(threshold['filas'])
    for col, value in {3: 'TOTAL / P₀ⁱ PONDERADO', 4: f'=SUM(D9:D{total-1})',
                       5: f'=D{total}/10000', 6: f'=IF(D{total}>0,SUM(G9:G{total-1})/D{total},"")',
                       7: f'=SUM(G9:G{total-1})', 11: f'=SUM(K9:K{total-1})'}.items():
        uses.cell(total, col, value)
    for cell in uses[total][:11]:
        cell.fill = PatternFill('solid', fgColor=PALE)
        cell.font = Font(name='Aptos', size=10, bold=True, color=NAVY)
    uses.cell(total, 6).number_format = '0.000'
    uses.cell(total, 11).number_format = '0.00%'
    for col in (4, 5, 7):
        uses.cell(total, col).number_format = '#,##0.000'
    uses.cell(total+2, 1, 'Superficie máscara MDT (km²)')
    uses.cell(total+2, 4, basin['area_km2'])
    uses.cell(total+3, 1, 'Diferencia vectorial menos máscara (m²)')
    uses.cell(total+3, 4, f'=D{total}-D{total+2}*1000000')
    uses.cell(total+5, 1, 'Hipótesis: pendiente <3 % y práctica R/N donde corresponda; revisa las filas aplicadas.')
    for col, width in {'A': 34, 'B': 21, 'C': 43, 'D': 18, 'E': 15, 'F': 16,
                       'G': 19, 'H': 10, 'I': 14, 'J': 13, 'K': 15}.items():
        uses.column_dimensions[col].width = width
    uses.freeze_panes = 'D9'
    uses.auto_filter.ref = f'A8:K{total-1}'

    # Reference table and interpolation controls remain visible for auditing.
    _banner(source, 'Tabla YT por Cv y controles del cálculo')
    _band(source, 6, '01  FUENTES Y CRITERIOS')
    source['A8'] = 'Cuenca y cotas: MDT, máscara y dirección D8 guardados por DRENIA.'
    source['A9'] = 'Usos: ' + str(landuse.get('fuente', 'GeoPackage seleccionado'))
    source['A10'] = 'P₀ⁱ: norma 5.2-IC, tabla 2.3. YT: tabla aportada para el estudio.'
    _band(source, 12, '02  FACTORES YT POR Cv')
    _table_header(source, 14, ['Cv', 2, 5, 10, 25, 50, 100, 500])
    for row, (cv_key, factors) in enumerate(sorted(_YT_ROWS.items()), 15):
        source.cell(row, 1, cv_key/100).number_format = '0.00'
        for col, factor in enumerate((factors[i] for i in (0, 1, 2, 3, 4, 5, 7)), 2):
            source.cell(row, col, factor).number_format = '0.000'
        if row % 2 == 0:
            for cell in source[row][:8]:
                cell.fill = PatternFill('solid', fgColor=PAPER)
    source['J14'] = 'Cv activo'
    source['K14'] = "='01 Resumen'!F15"
    source['J15'] = 'Fila inferior'
    source['K15'] = '=IF(OR(K14<0.3,K14>0.52),"",IFERROR(MATCH(K14,A15:A37,1),""))'
    source['J16'] = 'Fila superior'
    source['K16'] = '=IF(K15="","",MIN(23,K15+1))'
    source['J17'] = 'Peso lineal'
    source['K17'] = '=IF(K15="","",IF(K15=K16,0,(K14-INDEX(A15:A37,K15))*100))'
    source['A39'] = 'No se extrapola fuera de Cv 0,30–0,52. T200 no interviene en estos caudales.'
    for col in 'ABCDEFGH':
        source.column_dimensions[col].width = 18
    source.column_dimensions['A'].width = 25
    source.column_dimensions['I'].width = 5
    source.column_dimensions['J'].width = 23
    source.column_dimensions['K'].width = 18
    source.freeze_panes = 'B15'

    # Front sheet reproduces the mockup's hierarchy and presents all terms.
    _banner(main, 'Cuenca delimitada / Método racional 5.2-IC')
    main.column_dimensions['A'].width = 17
    for col in 'BCDEFGHIJK':
        main.column_dimensions[col].width = 16
    main.column_dimensions['D'].width = 18
    main.column_dimensions['E'].width = 18
    main.column_dimensions['J'].width = 19
    main.column_dimensions['K'].width = 19
    _card(main, 1, 3, 'CAUDAL DE DISEÑO T5', '=IF(ISNUMBER(J28),J28,"Pendiente")', TEAL)
    _card(main, 5, 7, 'CAUDAL DE DISEÑO T100', '=IF(ISNUMBER(J32),J32,"Pendiente")', BLUE)
    _card(main, 9, 11, 'CAUDAL DE DISEÑO T500', '=IF(ISNUMBER(J33),J33,"Pendiente")', ORANGE)
    _band(main, 11, '01  DATOS DE PARTIDA Y GEOMETRÍA')
    metrics = [
        ('A14', 'Superficie de cuenca', 'B15', basin['area_km2'], '0.000 "km²"', True),
        ('C14', 'Precipitación diaria media', 'D15', _number(inputs['lluvia_media_mm']), '0.000 "mm"', True),
        ('E14', 'Cv', 'F15', _number(inputs['cv']), '0.000', True),
        ('G14', 'I₁/Id', 'H15', _number(inputs['i1_id']), '0.000', True),
        ('I14', 'βm regional', 'K15', _number(inputs['beta_m']), '0.000', True),
        ('A17', 'Grupo de suelo', 'B18', threshold['grupo_suelo'], 'General', False),
        ('C17', 'L · recorrido D8', 'D18', _number(inputs['longitud_km']), '0.000 "km"', True),
        ('E17', 'J · desnivel / L', 'F18', _number(inputs['pendiente']), '0.00000', True),
        ('G17', 'Tc utilizado', 'H18', '=IF(B20<>"",IF(B20>0,B20,""),IF(OR(D18<=0,F18<=0),"",0.3*(D18/F18^0.25)^0.76))', '0.000 "h"', False),
        ('I17', 'P₀ⁱ ponderado', 'K18', f"='02 Usos SIOSE'!F{total}", '0.000 "mm"', False),
    ]
    for label_cell, label, value_cell, value, number_format, editable in metrics:
        main[label_cell] = label
        main[label_cell].font = Font(name='Aptos', size=9, color=GRAY)
        item = main[value_cell]
        item.value = value
        item.font = Font(name='Aptos', size=13, bold=True, color=NAVY)
        item.number_format = number_format
        if editable:
            item.fill = PatternFill('solid', fgColor=INPUT)
    main['A20'] = 'Tc manual (h)'
    main['A20'].font = Font(name='Aptos', size=9, color=GRAY)
    main['B20'] = _number(inputs['tc_h']) if inputs.get('tc_h') else None
    main['B20'].fill = PatternFill('solid', fgColor=INPUT)
    if channel:
        main['D20'] = f"Cabecera X {channel['cabecera_x']:.2f} · Y {channel['cabecera_y']:.2f}"
        main['D21'] = (f"Cotas: {channel['cota_cabecera_m']:.2f} → "
                       f"{channel['cota_vertido_m']:.2f} m · desnivel {channel['desnivel_m']:.2f} m")
    else:
        main['D20'] = 'L y J introducidos manualmente; sin cotas del MDT en esta exportación.'
    for cell in ('D20', 'D21'):
        main[cell].font = Font(name='Aptos', size=9, color=GRAY)
    _band(main, 23, '02  CÁLCULO POR PERIODO DE RETORNO')
    main['A24'] = 'Entradas manuales: Ft. YT según Cv · Pd = Pd media × YT · P₀ = P₀ inicial × βm × Ft.'
    main['A24'].font = Font(name='Aptos', size=9, color=GRAY)
    _table_header(main, 26, ['T', 'YT', 'Ft', 'Pd (mm)', 'Pd·Ka (mm)', 'P₀ (mm)',
                             'C', 'I (mm/h)', 'Kt', 'Q (m³/s)', 'Estado'])
    for row, period in enumerate(FLOW_PERIODS, 27):
        main.cell(row, 1, period)
        match = f"MATCH(A{row},'03 Fuentes y control'!$B$14:$H$14,0)"
        low = f"INDEX('03 Fuentes y control'!$B$15:$H$37,'03 Fuentes y control'!$K$15,{match})"
        high = f"INDEX('03 Fuentes y control'!$B$15:$H$37,'03 Fuentes y control'!$K$16,{match})"
        main.cell(row, 2, f"=IF('03 Fuentes y control'!$K$15=\"\",\"\",{low}*(1-'03 Fuentes y control'!$K$17)+{high}*'03 Fuentes y control'!$K$17)")
        ft = inputs.get('ft', {}).get(str(period), '')
        main.cell(row, 3, _number(ft) if str(ft).strip() else None)
        main.cell(row, 4, f'=IF(OR(B{row}="",C{row}="",C{row}<=0,$D$15<=0),"",B{row}*$D$15)')
        main.cell(row, 5, f'=IF(D{row}="","",D{row}*$B$39)')
        main.cell(row, 6, f'=IF(OR(C{row}="",C{row}<=0,$K$18="",$K$15<=0),"",$K$18*$K$15*C{row})')
        ratio = f'(E{row}/F{row})'
        main.cell(row, 7, f'=IF(OR(E{row}="",F{row}=""),"",IF(F{row}=0,1,IF(E{row}<=F{row},0,(({ratio}-1)*({ratio}+23))/({ratio}+11)^2)))')
        main.cell(row, 8, f'=IF(OR(E{row}="",$H$18="",$H$15<=0),"",E{row}/24*$H$15^(3.5287-2.5287*$H$18^0.1))')
        main.cell(row, 9, '=IF($H$18="","",$E$39)')
        main.cell(row, 10, f'=IF(AND(ISNUMBER(G{row}),ISNUMBER(H{row}),ISNUMBER(I{row})),G{row}*H{row}*$B$15*I{row}/3.6,"")')
        main.cell(row, 11, f'=IF(OR(C{row}="",C{row}<=0),"Falta Ft",IF(J{row}="","Revisar entradas","Calculado"))')
        main.cell(row, 3).fill = PatternFill('solid', fgColor=INPUT)
        for col in range(2, 11):
            main.cell(row, col).number_format = '0.0000'
        for cell in main[row][:11]:
            cell.font = Font(name='Aptos', size=10, color=NAVY,
                             bold=period in (5, 100, 500))
            cell.alignment = Alignment(vertical='center', horizontal='center')
            if period in (5, 100, 500) and cell.column != 3:
                cell.fill = PatternFill('solid', fgColor=PALE)
            elif period not in (5, 100, 500) and row % 2 == 1 and cell.column != 3:
                cell.fill = PatternFill('solid', fgColor=PAPER)
        main.row_dimensions[row].height = 25
    main['A34'] = 'Ft de T10 y T50 se interpola por el usuario. No se incluye T200.'
    main['A34'].font = Font(name='Aptos', size=9, color=GRAY)
    _band(main, 36, '03  TRAZABILIDAD DEL CÁLCULO')
    main['A38'] = 'Ka = 1 − log₁₀(A) / 15'
    main['B39'] = '=IF(B15<=0,"",IF(B15<1,1,1-LOG10(B15)/15))'
    main['D38'] = 'Kt = 1 + Tc^1,25 / (Tc^1,25 + 14)'
    main['E39'] = '=IF(H18="","",1+H18^1.25/(H18^1.25+14))'
    main['G38'] = 'Pd,ef = Pd × Ka'
    main['G39'] = 'C = f(Pd,ef / P₀) · I = f(Pd,ef, I₁/Id, Tc)'
    main['G40'] = 'Q = C × I × A × Kt / 3,6'
    main['A41'] = 'Tc = 0,3 × (L / J^0,25)^0,76'
    for cell in ('A38', 'D38', 'G38', 'G39', 'G40', 'A41'):
        main[cell].font = Font(name='Aptos', size=10, color=GRAY)
    for cell in ('B39', 'E39'):
        main[cell].number_format = '0.0000'
        main[cell].font = Font(name='Aptos', size=11, bold=True, color=TEAL)
    main['A43'] = 'Cálculo con las entradas actuales. Las celdas azules se pueden editar y las fórmulas se recalculan en Excel.'
    main['A43'].font = Font(name='Aptos', size=9, color=GRAY)
    main.freeze_panes = 'A27'
    main.sheet_view.showGridLines = False
    uses.sheet_view.showGridLines = False
    source.sheet_view.showGridLines = False
    main.print_options.horizontalCentered = True
    main.sheet_properties.pageSetUpPr.fitToPage = True
    main.page_setup.fitToWidth = 1
    main.page_setup.fitToHeight = 1
    main.print_area = 'A1:K43'
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path
