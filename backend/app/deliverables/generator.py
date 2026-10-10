"""Small dependency-free generators for the three fixed deliverables."""

from dataclasses import dataclass
from io import BytesIO
from typing import Any, Iterable, Mapping
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


@dataclass(frozen=True)
class DeliverableFile:
    filename: str
    content_type: str
    content: bytes


def generate_plan_docx(title: str, sections: Mapping[str, str], *, preserve_lines: bool = False) -> DeliverableFile:
    if not title.strip():
        raise ValueError("document title is required")
    if not sections:
        raise ValueError("document sections are required")
    for heading, content in sections.items():
        if not heading.strip() or not content.strip():
            raise ValueError("document section headings and content cannot be empty")

    paragraphs = [f"<w:p><w:r><w:t>{escape(title)}</w:t></w:r></w:p>"]
    for heading, content in sections.items():
        paragraphs.append(f"<w:p><w:r><w:t>{escape(heading)}</w:t></w:r></w:p>")
        if preserve_lines:
            for line in content.splitlines() or [content]:
                paragraphs.append(f"<w:p><w:r><w:t>{escape(line)}</w:t></w:r></w:p>")
        else:
            paragraphs.append(f"<w:p><w:r><w:t>{escape(content)}</w:t></w:r></w:p>")
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(paragraphs)}<w:sectPr/></w:body></w:document>"
    )
    content = _zip_bytes(
        {
            "[Content_Types].xml": _docx_content_types(),
            "_rels/.rels": _root_rels("word/document.xml"),
            "word/document.xml": document,
        }
    )
    return DeliverableFile(
        "event-plan.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content,
    )


def generate_budget_xlsx(rows: Iterable[Mapping[str, Any]]) -> DeliverableFile:
    return _generate_xlsx("预算", ["项目", "数量", "单价", "小计", "来源"] , rows, "budget.xlsx")


def generate_execution_tasks_xlsx(rows: Iterable[Mapping[str, Any]]) -> DeliverableFile:
    return _generate_xlsx("执行任务", ["任务", "负责人", "截止时间", "状态", "附件"], rows, "execution-tasks.xlsx")


def _generate_xlsx(
    sheet_title: str,
    headers: list[str],
    rows: Iterable[Mapping[str, Any]],
    filename: str,
) -> DeliverableFile:
    matrix = [headers]
    for row in rows:
        missing_headers = [header for header in headers if header not in row]
        if missing_headers:
            raise ValueError(f"missing required spreadsheet columns: {', '.join(missing_headers)}")
        null_headers = [header for header in headers if row[header] is None]
        if null_headers:
            raise ValueError(f"spreadsheet columns cannot be null: {', '.join(null_headers)}")
        matrix.append([str(row[header]) for header in headers])
    if len(matrix) == 1:
        raise ValueError("at least one spreadsheet data row is required")
    cells: list[str] = []
    for row_index, row in enumerate(matrix, start=1):
        row_cells = []
        for column_index, value in enumerate(row, start=1):
            reference = f"{_column_name(column_index)}{row_index}"
            row_cells.append(
                f'<c r="{reference}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
            )
        cells.append(f'<row r="{row_index}">{''.join(row_cells)}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(cells)}</sheetData></worksheet>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(sheet_title)}" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    content = _zip_bytes(
        {
            "[Content_Types].xml": _xlsx_content_types(),
            "_rels/.rels": _root_rels("xl/workbook.xml"),
            "xl/workbook.xml": workbook,
            "xl/_rels/workbook.xml.rels": (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                '</Relationships>'
            ),
            "xl/worksheets/sheet1.xml": sheet,
        }
    )
    return DeliverableFile(
        filename,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content,
    )


def _zip_bytes(files: Mapping[str, str]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content.encode("utf-8"))
    return output.getvalue()


def _column_name(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _root_rels(target: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="{target}"/>'
        '</Relationships>'
    )


def _docx_content_types() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )


def _xlsx_content_types() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )
