"""Populate the shipped blank ledger template; never uses Payroll worksheets."""
from copy import copy
from datetime import datetime
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def build_workbook(year, rows, details, t):
    workbook = load_workbook(Path(__file__).resolve().parents[3]/'export_templates'/'salary_records.xlsx')
    summary, detail = workbook.worksheets
    summary.title=t('salary_record.summary_sheet')
    detail.title=t('salary_record.detail_sheet')
    headers = [
        ['employee','employee','entity','currency','gross_amount','employee_mpf','net_amount','recorded_months','missing_months'],
        ['employee','employee','entity','month','currency','gross_amount','employee_mpf','net_amount','net_difference','remarks','evidence'],
    ]
    values = [
        [[r['employee'].employee_no, r['employee'].chinese_name or r['employee'].english_name,
          r['entity'] or t('salary_record.choose_entity'), r['currency'],
          *[r['amounts'][f] for f in ('gross_amount','employee_mpf','net_amount')],
          ', '.join(r['months']), ', '.join(r['missing'])] for r in rows],
        [[r.employee.employee_no, r.employee.chinese_name or r.employee.english_name,
          r.payroll_entity.display_name, datetime.strptime(r.year_month,'%Y-%m'),r.currency,
          r.gross_amount,r.employee_mpf,r.net_amount,r.gross_amount-r.employee_mpf-r.net_amount,
          r.remarks or '',r.evidence_document.original_filename if r.evidence_document else ''] for r in details]
    ]
    for index,sheet in enumerate((summary,detail)):
        sheet['A2']=f"{t('salary_record.annual') if index==0 else t('salary_record.detail_sheet')} | {year}-04 — {year+1}-03"
        sheet['A3']=t('salary_record.boundary')
        sheet['A4']=t('salary_record.annual_rule') if index==0 else t('salary_record.mpf_rule')
        for note_row in (3,4):
            sheet.merge_cells(start_row=note_row,start_column=1,end_row=note_row,end_column=len(headers[index]))
            sheet.cell(note_row,1).alignment=Alignment(wrap_text=True,vertical='center')
            sheet.row_dimensions[note_row].height=32
        # Notes remain outside the tabular data. No employee text can become an Excel formula.
        for col,key in enumerate(headers[index],1):
            sheet.cell(5,col,t('salary_record.'+key))
        sheet.cell(5,1,t('salary_record.employee')+' ID')
        for row_num,row in enumerate(values[index],6):
            for col,value in enumerate(row,1):
                cell=sheet.cell(row_num,col)
                cell._style=copy(sheet.cell(6,col)._style)
                cell.value=value
                if isinstance(value,str):
                    cell.data_type='s'
                numeric = 5<=col<=7 if index==0 else 6<=col<=9
                cell.alignment=Alignment(vertical='center',horizontal='right' if numeric else 'left',wrap_text=col>=len(row)-1)
                if numeric:
                    cell.number_format='#,##0.00;[Red](#,##0.00);0.00'
                if index==1 and col==4:
                    cell.number_format='yyyy-mm'
                if row_num%2==0:
                    cell.fill=PatternFill('solid',fgColor='F1F6F5')
            sheet.row_dimensions[row_num].height=max(30,min(100,15*(1+max(len(str(v or ''))//28 for v in row[-2:]))))
        sheet.column_dimensions['A'].width=16
        sheet.column_dimensions['B'].width=25
        sheet.column_dimensions['C'].width=30
        sheet.column_dimensions['D' if index==0 else 'E'].width=12
        sheet.column_dimensions[get_column_letter(len(headers[index])-1)].width=38
        sheet.column_dimensions[get_column_letter(len(headers[index]))].width=42
        sheet.freeze_panes='C6'
        sheet.auto_filter.ref=f'A5:{get_column_letter(len(headers[index]))}{max(5,len(values[index])+5)}'
        sheet.print_options.horizontalCentered=False
        sheet.sheet_properties.pageSetUpPr.fitToPage=True
        sheet.page_setup.orientation='landscape'
        sheet.page_setup.paperSize=sheet.PAPERSIZE_A3
        sheet.page_setup.fitToWidth=1
        sheet.page_setup.fitToHeight=0
        sheet.print_title_rows='1:5'
    return workbook
