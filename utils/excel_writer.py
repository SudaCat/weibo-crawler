"""
Excel 写入模块
将爬虫结果写入 .xlsx 文件，自动调整列宽、格式化表头
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import (
    EXCEL_HEADERS,
    EXCEL_FILENAME_PREFIX,
    EXCEL_COL_WIDTHS,
    RESULT_DIR,
)
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def write_results(
    data: list[dict],
    output_path: Optional[Path] = None,
) -> Path:
    """
    将爬虫结果写入 Excel 文件

    Args:
        data: 爬虫结果列表，每条为 dict，键与 EXCEL_HEADERS 对应
        output_path: 输出文件路径（可选，默认自动生成带时间戳的文件名）

    Returns:
        实际写入的文件路径
    """
    # ============================================================
    # 1. 确定输出路径
    # ============================================================
    if output_path is None:
        RESULT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{EXCEL_FILENAME_PREFIX}_{timestamp}.xlsx"
        output_path = RESULT_DIR / filename
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # 2. 创建工作簿
    # ============================================================
    wb = Workbook()
    ws = wb.active
    ws.title = "爬虫结果"

    # ============================================================
    # 3. 写入表头（带样式）
    # ============================================================
    header_font = Font(name="微软雅黑", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    for col_idx, header in enumerate(EXCEL_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # ============================================================
    # 4. 写入数据
    # ============================================================
    data_font = Font(name="微软雅黑", size=10)
    data_alignment = Alignment(vertical="center", wrap_text=True)

    for row_idx, record in enumerate(data, start=2):
        for col_idx, header in enumerate(EXCEL_HEADERS, start=1):
            value = record.get(header, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = data_font
            cell.alignment = data_alignment
            cell.border = thin_border

    # ============================================================
    # 5. 设置列宽
    # ============================================================
    for col_idx, header in enumerate(EXCEL_HEADERS, start=1):
        col_letter = get_column_letter(col_idx)
        width = EXCEL_COL_WIDTHS.get(header, 15)
        ws.column_dimensions[col_letter].width = width

    # 设置行高
    ws.row_dimensions[1].height = 25  # 表头行高
    for row_idx in range(2, len(data) + 2):
        ws.row_dimensions[row_idx].height = 20

    # ============================================================
    # 6. 冻结首行 & 保存
    # ============================================================
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions  # 自动筛选

    wb.save(str(output_path))
    logger.info(f"✅ 爬虫结果已写入: {output_path}（共 {len(data)} 条）")

    return output_path