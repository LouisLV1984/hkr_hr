from pathlib import Path
from shutil import copy2

from docx import Document


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT.parent
TEMPLATE_ROOT = PROJECT_ROOT / "contract_templates"


TEMPLATE_SOURCES = {
    "HKR_SITE_Employment_Contract_Template.docx": "v2 clean - Proposed SITE Employment Contract Template 20250501.docx",
    "HKR_OFFICE_Employment_Contract_Template.docx": "v2 clean - Proposed OFFICE Employment Contract Template 20250501.docx",
}


def replace_text(container, replacements):
    for paragraph in container.paragraphs:
        text = paragraph.text
        new_text = text
        for old, new in replacements.items():
            new_text = new_text.replace(old, new)

        if "受僱日期" in new_text and new_text.startswith("自【"):
            new_text = (
                "自{{ start_year }}年{{ start_month }}月{{ start_day }}日"
                "（“受僱日期”）起生效，僱傭期限至僱員65歲生日，屆時雙方酌情商議是否續約。"
            )
        if "部【" in new_text and "崗" in new_text:
            new_text = "{{ department_text }}{{ position_text }}崗。"
        if "僱員的基本薪金為每月HK$" in new_text:
            new_text = "僱員的基本薪金為{{ salary_text }}，其中包括膳食津貼、交通津貼及通訊津貼 ；"

        if new_text != text:
            paragraph.text = new_text

    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                replace_text(cell, replacements)


def remove_site_probation(doc):
    remove_next = False
    for paragraph in list(doc.paragraphs):
        text = paragraph.text.strip()
        if text == "試用期":
            paragraph._element.getparent().remove(paragraph._element)
            remove_next = True
            continue
        if remove_next and text.startswith("僱員的試用期"):
            paragraph._element.getparent().remove(paragraph._element)
            remove_next = False


def populate_signature_placeholders(doc):
    if not doc.tables:
        return
    table = doc.tables[-1]
    if len(table.rows) < 4 or len(table.columns) < 2:
        return
    table.cell(1, 1).text = "{{ employee_name }}"
    table.cell(2, 1).text = "{{ primary_identity_no }}"


def build_template(source_name, output_name):
    source = SOURCE_ROOT / source_name
    output = TEMPLATE_ROOT / output_name
    if not source.exists():
        raise FileNotFoundError(source)

    TEMPLATE_ROOT.mkdir(parents=True, exist_ok=True)
    copy2(source, output)
    doc = Document(output)
    replacements = {
        "【日期】": "{{ contract_date }}",
        "【1/5/2025】": "{{ contract_date }}",
        "【法定姓名】": "{{ employee_name }}",
        "【姓名】": "{{ employee_name }}",
        "致：【姓】【先生/女士】": "致：{{ salutation_name }}{{ salutation }}",
        "【地盘】": "{{ work_location }}",
        "【總部辦公室】": "{{ work_location }}",
        "【3個月】": "{{ probation_months_text }}",
        "【 7 天】": "{{ contract_annual_leave_text }}",
        "【7天】": "{{ contract_annual_leave_text }}",
    }
    replace_text(doc, replacements)
    if "SITE" in output_name:
        remove_site_probation(doc)
    populate_signature_placeholders(doc)
    doc.save(output)
    return output


def main():
    bad_sample = TEMPLATE_ROOT / "MVP Employment Contract Template.docx"
    if bad_sample.exists():
        bad_sample.unlink()
    for output_name, source_name in TEMPLATE_SOURCES.items():
        print(build_template(source_name, output_name))


if __name__ == "__main__":
    main()
