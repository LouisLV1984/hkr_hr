"""Local-only synthetic register UI fixture; no production database or files."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_salary_records import SalaryRecordTests

def main():
    fixture=SalaryRecordTests()
    fixture.setUp()
    try:
        for index,group in enumerate(('site_daily','site_monthly','management'),1):
            fixture.employee(group,index)
        fixture.app.config['CSRF_ENABLED']=True
        fixture.app.run(host='127.0.0.1',port=8767,use_reloader=False)
    finally:
        fixture.tearDown()

if __name__=='__main__': main()
