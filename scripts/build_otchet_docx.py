#!/usr/bin/env python3
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


OUT = Path(__file__).resolve().parent.parent / "docs" / "Otchet-integracionnoe-testirovanie.docx"


def set_run_font(run, size=14, bold=False, italic=False, name="Times New Roman"):
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)
    run.font.name = name
    run.font.color.rgb = RGBColor(0, 0, 0)
    r = run._element.get_or_add_rPr()
    rFonts = r.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = r.makeelement(qn("w:rFonts"), {})
        r.append(rFonts)
    rFonts.set(qn("w:ascii"), name)
    rFonts.set(qn("w:hAnsi"), name)
    rFonts.set(qn("w:cs"), name)
    rFonts.set(qn("w:eastAsia"), name)


def style_paragraph(p, size=14, bold=False, italic=False, align="left", space_after=6, space_before=0, first_line=True):
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    if first_line and align == "justify":
        p.paragraph_format.first_line_indent = Cm(1.25)
    else:
        p.paragraph_format.first_line_indent = Cm(0)
    align_map = {
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }
    p.alignment = align_map[align]
    for run in p.runs:
        set_run_font(run, size=size, bold=bold, italic=italic)


def add_title(doc, text):
    p = doc.add_paragraph()
    p.add_run(text)
    style_paragraph(p, size=16, bold=True, align="center", space_after=12, first_line=False)


def add_heading(doc, text):
    p = doc.add_paragraph()
    p.add_run(text)
    style_paragraph(p, size=14, bold=True, align="left", space_before=12, space_after=8, first_line=False)


def add_subheading(doc, text):
    p = doc.add_paragraph()
    p.add_run(text)
    style_paragraph(p, size=14, bold=True, align="left", space_before=8, space_after=6, first_line=False)


def add_body(doc, text):
    p = doc.add_paragraph()
    p.add_run(text)
    style_paragraph(p, size=14, align="justify", space_after=6)


def add_meta(doc, text):
    p = doc.add_paragraph()
    p.add_run(text)
    style_paragraph(p, size=14, align="center", space_after=4, first_line=False)


def add_bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    p.clear()
    p.add_run(text)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    p.paragraph_format.left_indent = Cm(1.25)
    for run in p.runs:
        set_run_font(run, size=14)


def add_numbered(doc, text):
    p = doc.add_paragraph(style="List Number")
    p.clear()
    p.add_run(text)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    p.paragraph_format.left_indent = Cm(1.25)
    for run in p.runs:
        set_run_font(run, size=14)


def shade_cell(cell, color="D9E2F3"):
    tc = cell._tePr if False else cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = tcPr.find(qn("w:shd"))
    if shd is None:
        shd = tcPr.makeelement(qn("w:shd"), {})
        tcPr.append(shd)
    shd.set(qn("w:fill"), color)
    shd.set(qn("w:val"), "clear")


def set_cell_border(cell):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn("w:tcBorders"))
    if tcBorders is None:
        tcBorders = tcPr.makeelement(qn("w:tcBorders"), {})
        tcPr.append(tcBorders)
    for edge in ("top", "left", "bottom", "right"):
        el = tcBorders.find(qn(f"w:{edge}"))
        if el is None:
            el = tcBorders.makeelement(qn(f"w:{edge}"), {})
            tcBorders.append(el)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")


def fill_cell(cell, text, bold=False, size=11):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold)
    set_cell_border(cell)


def add_table(doc, headers, rows, col_widths=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    for i, h in enumerate(headers):
        fill_cell(table.rows[0].cells[i], h, bold=True, size=11)
        shade_cell(table.rows[0].cells[i], "D9E2F3")
    for r_i, row in enumerate(rows):
        for c_i, val in enumerate(row):
            fill_cell(table.rows[r_i + 1].cells[c_i], val, size=11)
    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph()


def add_code_block(doc, lines):
    for line in lines:
        p = doc.add_paragraph()
        p.add_run(line)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.left_indent = Cm(1)
        p.paragraph_format.first_line_indent = Cm(0)
        for run in p.runs:
            set_run_font(run, size=12, name="Courier New")
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(6)


def scenario_table(doc, rows):
    add_table(doc, ["Поле", "Содержание"], rows, col_widths=[4.5, 12.0])


def build():
    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(3)
        section.right_margin = Cm(1.5)

    styles = doc.styles["Normal"]
    styles.font.name = "Times New Roman"
    styles.font.size = Pt(14)
    styles._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")

    add_title(doc, "Отчёт по интеграционному тестированию")
    add_meta(doc, "Дисциплина: Интеграционное тестирование")
    add_meta(doc, "Проект: Users API + Orders API (user-order-services)")
    add_meta(doc, "Автор: sssiqwel")

    add_heading(doc, "1. Постановка задачи")
    add_body(
        doc,
        "По заданию необходимо ознакомиться с требованиями к проекту, в котором проводится интеграционное тестирование; "
        "на основе требований разработать не менее пяти тестовых сценариев, покрывающих ключевую функциональность системы; "
        "оценить сценарии на полноту и корректность; улучшить их так, чтобы они были максимально эффективными "
        "и покрывали основные сценарии использования; подготовить отчёт, включающий разработанные сценарии, их оценку и предложенные улучшения.",
    )
    add_body(
        doc,
        "В качестве системы выбран учебный проект user-order-services: два HTTP-сервиса с синхронным межсервисным вызовом. "
        "Это классическая постановка для интеграционного тестирования. Ниже приведены требования, исходные сценарии, "
        "оценка их полноты и исправленный набор.",
    )

    add_heading(doc, "2. Требования к системе")
    add_body(doc, "Система состоит из двух микросервисов.")
    add_table(
        doc,
        ["Сервис", "Порт", "Назначение"],
        [
            ["Users API", "8001", "Создание и получение пользователя"],
            [
                "Orders API",
                "8002",
                "Создание и получение заказа; при этом запрашивает пользователя в Users API по user_id",
            ],
        ],
        col_widths=[3.5, 2.5, 10.5],
    )
    add_code_block(
        doc,
        [
            "клиент ──► Orders API ──HTTP GET /api/v1/users/{id}──► Users API",
            "                │",
            "                └── 201/200 + данные пользователя",
            "                    404 если пользователя нет",
            "                    503 если Users API недоступен",
        ],
    )

    add_subheading(doc, "2.1. Функциональные требования")
    add_body(doc, "Users API")
    add_bullet(doc, "GET /health — сервис жив.")
    add_bullet(doc, "GET /api/v1/users — список пользователей.")
    add_bullet(doc, "GET /api/v1/users/{id} — пользователь по id; 404, если нет; 422 при невалидном id.")
    add_bullet(doc, "POST /api/v1/users — создать пользователя (нужен Bearer-токен).")
    add_bullet(doc, "Успех: 201 и заголовок Location.")
    add_bullet(doc, "Без токена или неверный токен: 401.")
    add_bullet(doc, "Email уже занят: 409.")
    add_bullet(doc, "Невалидное тело: 422.")
    add_bullet(doc, "name: 1–100 символов, не из одних пробелов, обрезаются края.")
    add_bullet(doc, "email нормализуется к нижнему регистру и должен быть уникален.")
    add_bullet(doc, "Неизвестные поля запрещены. Идентификатор назначает сервер.")
    add_body(doc, "Orders API")
    add_bullet(doc, "GET /health — сервис жив.")
    add_bullet(doc, "GET /api/v1/orders — список заказов; в каждом заказе вложенный user из Users API.")
    add_bullet(doc, "GET /api/v1/orders/{id} — заказ по id с актуальными данными пользователя.")
    add_bullet(
        doc,
        "POST /api/v1/orders — создать заказ (нужен Bearer-токен). Перед записью сервис вызывает GET {USER_SERVICE_URL}/api/v1/users/{user_id}.",
    )
    add_bullet(doc, "Успех: 201, Location и вложенный user.")
    add_bullet(doc, "Пользователя нет: 404, заказ не создаётся.")
    add_bullet(doc, "Users API недоступен, таймаут или 5xx: 503, заказ не создаётся.")
    add_bullet(doc, "Без токена: 401. Невалидное тело: 422.")
    add_bullet(doc, "item — непустая строка; quantity — от 1 до 1000; user_id ≥ 1.")

    add_subheading(doc, "2.2. Нефункциональные и сквозные требования")
    add_bullet(doc, "Изменяющие запросы требуют Authorization: Bearer secret-token.")
    add_bullet(doc, "Каждый ответ содержит X-Request-ID (эхо клиентского значения или сгенерированный UUID).")
    add_bullet(doc, "Ответы Orders API, которые ходили в Users API, содержат X-User-Service-Time-Ms.")
    add_bullet(
        doc,
        "Межсервисный вызов должен укладываться в SLO: менее 500 мс по заголовку, весь HTTP-ответ — менее 1000 мс.",
    )
    add_bullet(doc, "Таймаут вызова Users API — 2 секунды (USER_SERVICE_TIMEOUT).")
    add_bullet(
        doc,
        "Данные хранятся в памяти процесса: после перезапуска Users API снова два стартовых пользователя, заказов нет.",
    )

    add_subheading(doc, "2.3. Ключевые точки интеграции")
    add_numbered(doc, "Успешный межсервисный вызов при создании заказа.")
    add_numbered(doc, "Повторный запрос пользователя при чтении заказа.")
    add_numbered(doc, "Пользователь не найден → 404, побочных записей нет.")
    add_numbered(doc, "Users API недоступен → 503, заказ не сохраняется.")
    add_numbered(doc, "Авторизация на изменяющих операциях.")
    add_numbered(doc, "Валидация входных данных.")
    add_numbered(doc, "Время отклика межсервисного вызова.")

    add_heading(doc, "3. Тестовые сценарии (первая версия)")
    add_body(
        doc,
        "Исходный набор из пяти сценариев составлен по требованиям до оценки полноты. "
        "Формат: идентификатор, цель, предусловия, шаги, ожидаемый результат.",
    )

    add_subheading(doc, "TS-01. Успешное создание заказа существующему пользователю")
    scenario_table(
        doc,
        [
            ["Тип", "Позитивный, интеграционный"],
            ["Приоритет", "Высокий"],
            [
                "Цель",
                "Проверить, что Orders API запрашивает пользователя в Users API и создаёт заказ с вложенными данными пользователя",
            ],
            ["Предусловия", "Оба сервиса запущены. Есть валидный токен secret-token."],
            [
                "Шаги",
                '1. POST /api/v1/users с телом {"name":"Мария Смирнова","email":"maria@example.com"} и заголовком Authorization. 2. POST /api/v1/orders с телом {"user_id": <id из шага 1>, "item":"Настольная лампа","quantity":2} и тем же токеном.',
            ],
            [
                "Ожидаемый результат",
                "Шаг 1: HTTP 201, в ответе есть id, name, email. Шаг 2: HTTP 201, user_id совпадает с созданным пользователем, поле user содержит те же id, name, email.",
            ],
        ],
    )

    add_subheading(doc, "TS-02. Создание заказа несуществующему пользователю")
    scenario_table(
        doc,
        [
            ["Тип", "Негативный, интеграционный"],
            ["Приоритет", "Высокий"],
            ["Цель", "Проверить, что заказ не создаётся, если Users API отвечает 404"],
            ["Предусловия", "Оба сервиса запущены. Токен валиден. Пользователя с id 999999 нет."],
            ["Шаги", '1. POST /api/v1/orders с телом {"user_id":999999,"item":"Кружка","quantity":1}.'],
            ["Ожидаемый результат", 'HTTP 404, тело {"detail":"User 999999 not found"}.'],
        ],
    )

    add_subheading(doc, "TS-03. Users API недоступен")
    scenario_table(
        doc,
        [
            ["Тип", "Негативный, интеграционный"],
            ["Приоритет", "Высокий"],
            ["Цель", "Проверить деградацию: Orders API не падает, а отвечает 503"],
            ["Предусловия", "Orders API запущен с USER_SERVICE_URL, указывающим на несуществующий хост."],
            ["Шаги", "1. POST /api/v1/orders с валидным телом и токеном."],
            ["Ожидаемый результат", "HTTP 503, в detail есть слово unavailable."],
        ],
    )

    add_subheading(doc, "TS-04. Получение заказа по id")
    scenario_table(
        doc,
        [
            ["Тип", "Позитивный, интеграционный"],
            ["Приоритет", "Средний"],
            ["Цель", "Проверить, что при чтении заказа сервис снова ходит в Users API"],
            ["Предусловия", "Выполнен TS-01, известен order_id."],
            ["Шаги", "1. GET /api/v1/orders/{order_id}."],
            ["Ожидаемый результат", "HTTP 200, в ответе есть вложенный объект user."],
        ],
    )

    add_subheading(doc, "TS-05. Создание заказа без токена")
    scenario_table(
        doc,
        [
            ["Тип", "Негативный"],
            ["Приоритет", "Средний"],
            ["Цель", "Проверить, что изменяющий запрос без Authorization отклоняется"],
            ["Предусловия", "Orders API запущен."],
            ["Шаги", "1. POST /api/v1/orders без заголовка Authorization."],
            ["Ожидаемый результат", "HTTP 401."],
        ],
    )

    add_heading(doc, "5. Оценка полноты и корректности сценариев")
    add_body(
        doc,
        "Исходные сценарии TS-01…TS-05 проверены на полноту относительно требований раздела 2. "
        "Минимум из пяти сценариев выполнен, ключевой happy path и основные ошибки интеграции (404, 503, 401) закрыты. "
        "При этом набор ещё не покрывает все обязательные точки и недостаточно конкретен для воспроизведения.",
    )
    add_table(
        doc,
        ["Замечание", "Где", "Почему это важно"],
        [
            [
                "Не проверено, что при 404/503 заказ не записался",
                "TS-02, TS-03",
                "Интеграционный тест обязан ловить побочный эффект, а не только код ответа.",
            ],
            [
                "Нет проверки заголовков Location, X-Request-ID, X-User-Service-Time-Ms",
                "TS-01, TS-04",
                "Они явно указаны в требованиях.",
            ],
            [
                "Нет сценария на список заказов",
                "—",
                "GET /orders тоже ходит в Users API на каждый элемент.",
            ],
            [
                "Нет 404 на несуществующий заказ",
                "—",
                "Нужно отличать «нет заказа» от «нет пользователя».",
            ],
            [
                "Нет валидации тела (422) и конфликта email (409)",
                "—",
                "Ключевые контрактные ошибки Users API и Orders API.",
            ],
            [
                "Нет неверного токена, только отсутствие заголовка",
                "TS-05",
                "В требованиях два разных ответа 401.",
            ],
            [
                "Нет SLO по времени межсервисного вызова",
                "—",
                "Прямое нефункциональное требование.",
            ],
            [
                "Нормализация email и имени не проверена",
                "—",
                "Иначе интеграция может сломаться на регистре email.",
            ],
            [
                "Предусловия и данные слишком общие",
                "все",
                "Сценарий должен быть воспроизводим без чтения кода.",
            ],
            [
                "TS-04 зависит от TS-01",
                "TS-04",
                "Сценарии лучше делать независимыми.",
            ],
        ],
        col_widths=[5.5, 3.0, 8.0],
    )
    add_body(doc, "Эти замечания — основание для раздела 6.")

    add_heading(doc, "6. Улучшенные тестовые сценарии")
    add_body(
        doc,
        "Учтены замечания по полноте и уже существующие автотесты в каталоге tests. "
        "Итого 10 сценариев: пять исходных переработаны и добавлены недостающие.",
    )

    add_subheading(doc, "ITS-01. Сквозное создание пользователя и заказа (happy path)")
    scenario_table(
        doc,
        [
            ["Тип / приоритет", "Позитивный, интеграционный / критический"],
            ["Связанные требования", "POST users 201, POST orders 201, вложенный user, Location"],
            [
                "Предусловия",
                "Users :8001 и Orders :8002 запущены. Токен secret-token. Email maria+its01@example.com свободен.",
            ],
            [
                "Тестовые данные",
                'User: {"name":"Мария Смирнова","email":"maria+its01@example.com"}. Order: {"user_id":<id>,"item":"Настольная лампа","quantity":2}.',
            ],
            [
                "Шаги",
                "1. POST http://127.0.0.1:8001/api/v1/users + Authorization: Bearer secret-token. 2. Сохранить id и тело пользователя. 3. POST http://127.0.0.1:8002/api/v1/orders с user_id из шага 2 и тем же токеном. 4. GET по заголовку Location ответа шага 3.",
            ],
            [
                "Ожидаемый результат",
                "Шаг 1: 201, id — целое, Location = /api/v1/users/{id}. Шаг 3: 201, user_id и user.{id,name,email} совпадают с шагом 2, item и quantity как в запросе, есть Location и X-User-Service-Time-Ms. Шаг 4: 200, тело совпадает с шагом 3.",
            ],
            [
                "Автотест",
                "tests/test_orders.py::test_create_and_get_order, tests/test_interservice.py::test_orders_service_fetches_user_by_id",
            ],
        ],
    )

    add_subheading(doc, "ITS-02. Повторный fetch пользователя при чтении заказа")
    scenario_table(
        doc,
        [
            ["Тип / приоритет", "Позитивный, интеграционный / высокий"],
            ["Связанные требования", "GET order ходит в Users API; заголовок времени вызова"],
            ["Предусловия", "Создан пользователь и заказ (данные как в ITS-01, изолированный email)."],
            [
                "Шаги",
                "1. GET /api/v1/orders/{id}. 2. Сравнить user с актуальным GET /api/v1/users/{user_id}.",
            ],
            [
                "Ожидаемый результат",
                "200; user полностью совпадает с Users API; заголовок X-User-Service-Time-Ms присутствует и ≥ 0.",
            ],
            ["Автотест", "tests/test_interservice.py::test_orders_service_fetches_user_by_id"],
        ],
    )

    add_subheading(doc, "ITS-03. Заказ на несуществующего пользователя: 404 и нет записи")
    scenario_table(
        doc,
        [
            ["Тип / приоритет", "Негативный, интеграционный / критический"],
            [
                "Предусловия",
                "Оба сервиса живы. Пользователя 999999 нет. Известно число заказов до шага 1 (GET /api/v1/orders).",
            ],
            [
                "Шаги",
                '1. POST /api/v1/orders {"user_id":999999,"item":"Кружка","quantity":1} с токеном. 2. GET /api/v1/orders.',
            ],
            [
                "Ожидаемый результат",
                'Шаг 1: 404, {"detail":"User 999999 not found"}. Шаг 2: список той же длины, заказа с user_id=999999 нет.',
            ],
            ["Автотест", "tests/test_orders.py::test_create_order_for_missing_user_returns_404"],
        ],
    )

    add_subheading(doc, "ITS-04. Users API недоступен: 503, заказ не создаётся")
    scenario_table(
        doc,
        [
            ["Тип / приоритет", "Негативный, интеграционный / критический"],
            [
                "Предусловия",
                "Отдельный экземпляр Orders API с USER_SERVICE_URL=http://127.0.0.1:9 (порт закрыт). Своё пустое хранилище заказов.",
            ],
            ["Шаги", "1. POST /api/v1/orders с валидным телом и токеном. 2. GET /api/v1/orders."],
            [
                "Ожидаемый результат",
                "Шаг 1: 503, detail содержит unavailable. Шаг 2: 200 и пустой список — запись не появилась. Сервис заказов при этом сам отвечает на /health.",
            ],
            ["Автотест", "tests/test_interservice.py::test_orders_return_503_when_users_service_is_unavailable"],
        ],
    )

    add_subheading(doc, "ITS-05. SLO времени межсервисного вызова")
    scenario_table(
        doc,
        [
            ["Тип / приоритет", "Нефункциональный, интеграционный / высокий"],
            ["Предусловия", "Оба сервиса на localhost, создан заказ. SLO = 500 мс."],
            [
                "Шаги",
                "1. GET /api/v1/orders/{id}. 2. Прочитать X-User-Service-Time-Ms и полное время ответа клиента.",
            ],
            [
                "Ожидаемый результат",
                "200; 0 ≤ X-User-Service-Time-Ms < 500; полное время ответа < 1000 мс.",
            ],
            ["Автотест", "tests/test_interservice.py::test_user_fetch_response_time_is_within_slo"],
        ],
    )

    add_subheading(doc, "ITS-06. Авторизация: нет заголовка и неверный токен")
    scenario_table(
        doc,
        [
            ["Тип / приоритет", "Негативный / высокий"],
            ["Предусловия", "Оба сервиса живы."],
            [
                "Шаги",
                "1. POST /api/v1/users без Authorization. 2. POST /api/v1/users с Authorization: Bearer wrong-token. 3. Те же два варианта для POST /api/v1/orders.",
            ],
            [
                "Ожидаемый результат",
                "Все четыре запроса: 401. Для Users: WWW-Authenticate: Bearer; detail = Missing Authorization header / Invalid token. Пользователь и заказ не создаются.",
            ],
            [
                "Автотест",
                "test_create_user_without_valid_token_returns_401, test_create_order_without_valid_token_returns_401",
            ],
        ],
    )

    add_subheading(doc, "ITS-07. Конфликт email и нормализация данных пользователя")
    scenario_table(
        doc,
        [
            ["Тип / приоритет", "Негативный + позитивный / средний"],
            ["Предусловия", "Users API жив, токен валиден."],
            [
                "Шаги",
                '1. POST /users с {"name":"  Мария  ","email":"  Maria@Example.COM  "}. 2. Повторный POST /users с тем же email в другом регистре.',
            ],
            [
                "Ожидаемый результат",
                "Шаг 1: 201, name=Мария, email=maria@example.com. Шаг 2: 409, в detail фигурирует нормализованный email.",
            ],
            [
                "Автотест",
                "test_create_user_normalizes_email_and_name, test_create_user_duplicate_email_returns_409",
            ],
        ],
    )

    add_subheading(doc, "ITS-08. Валидация входа: 422 на обоих сервисах")
    scenario_table(
        doc,
        [
            ["Тип / приоритет", "Негативный / средний"],
            [
                "Шаги",
                "Users: пустое имя, пробелы в имени, не-email, нет email, лишнее поле. Orders: пустой item, quantity=0, user_id=0, нет user_id, лишнее поле. Все с валидным токеном.",
            ],
            ["Ожидаемый результат", "Каждый запрос — 422. Записи не создаются."],
            [
                "Автотест",
                "test_create_user_invalid_payload_returns_422, test_create_order_invalid_payload_returns_422",
            ],
        ],
    )

    add_subheading(doc, "ITS-09. 404 на отсутствующие ресурсы")
    scenario_table(
        doc,
        [
            ["Тип / приоритет", "Негативный / средний"],
            ["Шаги", "1. GET /api/v1/users/999999. 2. GET /api/v1/orders/999999."],
            [
                "Ожидаемый результат",
                "404, User 999999 not found / Order 999999 not found. Это не 503 и не путается с ITS-03.",
            ],
            ["Автотест", "test_get_missing_user_returns_404, test_get_missing_order_returns_404"],
        ],
    )

    add_subheading(doc, "ITS-10. Список заказов обогащается пользователями; трассировка request-id")
    scenario_table(
        doc,
        [
            ["Тип / приоритет", "Позитивный, интеграционный / средний"],
            ["Предусловия", "Создан хотя бы один заказ."],
            [
                "Шаги",
                "1. GET /api/v1/orders. 2. GET /health на Users API с заголовком X-Request-ID: users-42.",
            ],
            [
                "Ожидаемый результат",
                "Шаг 1: 200, созданный заказ есть в списке, у каждого элемента есть user с id/name/email, есть X-User-Service-Time-Ms. Шаг 2: ответ эхом возвращает X-Request-ID: users-42.",
            ],
            ["Автотест", "test_list_orders_contains_created, test_request_id_is_echoed"],
        ],
    )

    add_heading(doc, "7. Матрица покрытия (после улучшений)")
    add_table(
        doc,
        ["Требование", "Сценарий"],
        [
            ["Создание пользователя", "ITS-01, ITS-07"],
            ["Создание заказа с fetch пользователя", "ITS-01"],
            ["Чтение заказа с повторным fetch", "ITS-02"],
            ["Список заказов с вложенным user", "ITS-10"],
            ["Пользователь не найден при создании заказа", "ITS-03"],
            ["Users API недоступен", "ITS-04"],
            ["SLO времени вызова", "ITS-05"],
            ["401: нет токена / неверный токен", "ITS-06"],
            ["409 duplicate email + нормализация", "ITS-07"],
            ["422 валидация", "ITS-08"],
            ["404 пользователя и заказа", "ITS-09"],
            ["X-Request-ID", "ITS-10"],
            ["Заказ не сохраняется при 404/503", "ITS-03, ITS-04"],
        ],
        col_widths=[9.0, 7.5],
    )
    add_body(
        doc,
        "Минимум «не менее 5» выполнен уже в разделе 3; после оценки покрытие доведено до ключевых позитивных, негативных и нефункциональных точек интеграции.",
    )

    add_heading(doc, "8. Связь с реализацией в репозитории")
    add_body(doc, "Сценарии не бумажные: они уже прогоняются автотестами.")
    add_code_block(
        doc,
        [
            "make install",
            "make test      # pytest; если сервисы не запущены, тесты поднимут их сами",
            "make newman    # Postman-коллекция",
            "make check     # pytest + newman",
        ],
    )
    add_table(
        doc,
        ["Сценарий отчёта", "pytest", "Postman"],
        [
            [
                "ITS-01, ITS-02",
                "test_interservice.py, test_orders.py",
                "Create order fetches user, Get order refreshes user",
            ],
            [
                "ITS-04",
                "test_orders_return_503_when_users_service_is_unavailable",
                "только pytest (изолированный Orders API)",
            ],
            [
                "ITS-05",
                "test_user_fetch_response_time_is_within_slo",
                "заголовок < 500 мс, ответ < 1000 мс",
            ],
            ["ITS-06…ITS-10", "test_users.py, test_orders.py", "соответствующие запросы коллекции"],
        ],
        col_widths=[4.0, 6.5, 6.0],
    )

    add_heading(doc, "9. Выводы")
    add_numbered(
        doc,
        "Свой вариант — проект user-order-services: два FastAPI-сервиса с синхронным HTTP-вызовом. Задание на сценарии ложится на него напрямую.",
    )
    add_numbered(
        doc,
        "Первая версия содержала 5 сценариев и закрывала happy path, 404, 503 и 401, но не проверяла побочные эффекты, заголовки, SLO, валидацию и изоляцию данных.",
    )
    add_numbered(
        doc,
        "По результатам оценки сценарии расширены до 10: добавлены побочные эффекты 404/503, SLO, оба варианта 401, 409, 422, различие 404 заказа и 404 пользователя, список заказов и трассировка.",
    )
    add_numbered(
        doc,
        "Улучшенные сценарии совпадают с автотестами репозитория, их можно демонстрировать прогоном make check.",
    )

    props = doc.core_properties
    props.author = "sssiqwel"
    props.last_modified_by = "sssiqwel"
    props.title = "Отчёт по интеграционному тестированию"
    props.comments = ""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
