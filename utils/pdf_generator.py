from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from datetime import datetime


def register_fonts():
    """Регистрация русских шрифтов для ReportLab"""

    # Попробуем найти русский шрифт в системе
    font_paths = [
        # Windows
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/times.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # macOS
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        # Текущая директория
        "fonts/DejaVuSans.ttf",
        "fonts/arial.ttf",
    ]

    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                # Регистрируем обычный шрифт
                pdfmetrics.registerFont(TTFont('RussianFont', font_path))
                print(f"✅ Используется шрифт: {font_path}")
                return 'RussianFont'
            except:
                continue

    # Если не нашли русский шрифт, скачиваем DejaVuSans
    try:
        import requests
        print("📥 Загружаем шрифт DejaVu Sans...")

        # URL для скачивания DejaVu Sans
        font_url = "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip"

        # Создаем папку для шрифтов
        os.makedirs('fonts', exist_ok=True)

        # Скачиваем и распаковываем (упрощенный вариант)
        # На практике лучше иметь шрифт локально

        print("⚠️ Русский шрифт не найден. Установите шрифт вручную.")
        print("Скачайте DejaVuSans.ttf и поместите в папку fonts/")

    except:
        pass

    print("⚠️ Используется стандартный шрифт (кириллица может не отображаться)")
    return 'Helvetica'


def generate_order_invoice(order, regenerate=False):
    """Генерация PDF для заказ-наряда"""

    # Регистрируем шрифты
    font_name = register_fonts()

    # Создаем PDF во временный файл
    filename = f"order_invoice_{order.order_id}.pdf"
    filepath = os.path.join('static', 'invoices', filename)

    if not regenerate and os.path.exists(filepath):
        return filepath

    # Создаем директорию если не существует
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except:
            pass

    doc = SimpleDocTemplate(filepath, pagesize=A4)
    story = []

    # Стили с русским шрифтом
    styles = getSampleStyleSheet()

    # Создаем стиль с русским шрифтом
    title_style = ParagraphStyle(
        'RussianTitle',
        parent=styles['Title'],
        fontName=font_name,
        fontSize=16,
        spaceAfter=30,
        alignment=1  # Center
    )

    heading_style = ParagraphStyle(
        'RussianHeading',
        parent=styles['Heading2'],
        fontName=font_name,
        fontSize=12,
        spaceAfter=12
    )

    normal_style = ParagraphStyle(
        'RussianNormal',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10
    )

    # Заголовок
    story.append(Paragraph("АВТОСЕРВИС 'МАСТЕР'", title_style))
    story.append(Paragraph(f"ЗАКАЗ-НАРЯД №{order.order_id}", title_style))
    story.append(Spacer(1, 20))

    # Получаем автомобиль (с учетом разных имен отношений)
    car = getattr(order, 'car', None) or getattr(order, 'car_info', None)

    if not car:
        story.append(Paragraph("Ошибка: автомобиль не найден", normal_style))
        doc.build(story)
        return filepath

    # Информация о клиенте и автомобиле
    client_data = [
        ["Клиент:", f"{car.owner.full_name}"],
        ["Телефон:", f"{car.owner.phone}"],
        ["Автомобиль:", f"{car.brand} {car.model} ({car.year})"],
        ["Госномер:", f"{car.license_plate}"],
        ["Дата приёмки:", f"{order.reception_date.strftime('%d.%m.%Y')}"],
        ["Статус:", f"{order.get_status_name()}"],
    ]

    client_table = Table(client_data, colWidths=[4 * cm, 10 * cm])
    client_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(client_table)
    story.append(Spacer(1, 20))

    # Работы по заказу
    story.append(Paragraph("Выполненные работы:", heading_style))

    works_data = [["№", "Наименование работы", "Стоимость", "Статус"]]

    for i, item in enumerate(order.order_items, 1):
        # Получаем работу (с учетом разных имен отношений)
        work = getattr(item, 'work', None) or getattr(item, 'work_info', None)
        work_name = work.work_name if work else "Неизвестная работа"
        work_cost = float(item.actual_cost or (work.base_cost if work else 0))

        works_data.append([
            str(i),
            work_name,
            f"{work_cost:.2f} руб.",
            item.get_status_name()
        ])

    works_table = Table(works_data, colWidths=[1 * cm, 9 * cm, 3 * cm, 3 * cm])
    works_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
    ]))

    story.append(works_table)
    story.append(Spacer(1, 20))

    # Использованные запчасти
    story.append(Paragraph("Использованные запчасти:", heading_style))

    parts_used = []
    for item in order.order_items:
        for part_usage in item.parts_used:
            parts_used.append(part_usage)

    if parts_used:
        parts_data = [["№", "Наименование", "Кол-во", "Цена", "Сумма"]]
        total_parts = 0

        for i, part_usage in enumerate(parts_used, 1):
            # Получаем запчасть (с учетом разных имен отношений)
            part = getattr(part_usage, 'part', None) or getattr(part_usage, 'part_info', None)
            part_name = part.part_name if part else "Неизвестная запчасть"

            part_sum = float(part_usage.quantity * part_usage.unit_price_at_time)
            total_parts += part_sum
            parts_data.append([
                str(i),
                part_name,
                str(part_usage.quantity),
                f"{float(part_usage.unit_price_at_time):.2f} руб.",
                f"{part_sum:.2f} руб."
            ])

        parts_table = Table(parts_data, colWidths=[1 * cm, 8 * cm, 2 * cm, 3 * cm, 3 * cm])
        parts_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ]))

        story.append(parts_table)
        story.append(Spacer(1, 10))
        story.append(Paragraph(f"Итого по запчастям: {total_parts:.2f} руб.", normal_style))
    else:
        story.append(Paragraph("Запчасти не использовались", normal_style))

    story.append(Spacer(1, 20))

    # Итоговая сумма
    try:
        total_cost = order.calculate_total()
        total_text = f"ИТОГО К ОПЛАТЕ: {total_cost:.2f} руб."
    except:
        total_cost = order.total_cost
        total_text = f"ИТОГО К ОПЛАТЕ: {float(total_cost):.2f} руб."

    total_style = ParagraphStyle(
        'RussianTotal',
        parent=styles['Heading2'],
        fontName=font_name,
        fontSize=14,
        textColor=colors.black,
        spaceBefore=10,
        spaceAfter=20
    )

    story.append(Paragraph(f"<b>{total_text}</b>", total_style))

    # Подписи
    story.append(Spacer(1, 40))
    signatures = [
        ["Исполнитель:", "_________________", "Клиент:", "_________________"],
        ["", "(подпись)", "", "(подпись)"]
    ]

    sig_table = Table(signatures, colWidths=[3 * cm, 5 * cm, 3 * cm, 5 * cm])
    sig_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    story.append(sig_table)

    # Создаем документ
    doc.build(story)

    return filepath