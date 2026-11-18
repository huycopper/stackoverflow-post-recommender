# ruff: noqa: E501
"""Team progress deck (Vietnamese) on the HUST template of an existing deck.

    uv run --with python-pptx --with pillow python scripts/slides/build_team_deck.py \n        TEMPLATE.pptx OUT.pptx numbers.json

TEMPLATE.pptx is a deck of the course template with at least 8 slides (slide 1 is the title,
slide 5 a content slide, slide 8 the closing slide); numbers.json comes from gather_numbers.py.
The slide text is written for the data as of 13/11/2026: read it again after the numbers change.
"""

import copy
import json
import sys

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

SRC, OUT, NUMBERS = sys.argv[1], sys.argv[2], sys.argv[3]
N = json.load(open(NUMBERS, encoding="utf-8"))
RED, INK, MUTED = "C00000", "262626", "595959"
GREY, AMBER, WHITE, LINE = "F4F2F2", "FDF1D8", "FFFFFF", "BFBFBF"


def vn(x):
    """1234567 -> 1.234.567 (Vietnamese thousands separator)."""
    return f"{x:,}".replace(",", ".")


def _leak_share():
    """Share of duplicate questions with a comment linking to their original (link_leak.py)."""
    leak = N.get("link_leak")
    if not leak:
        raise SystemExit("run scripts/link_leak.py first, then gather_numbers.py again")
    return leak["duplicates_with_leak"] / leak["duplicates"]


def pct(x, d=1):
    return f"{x * 100:.{d}f}".replace(".", ",") + "%"


prs = Presentation(SRC)
base = prs.slides[4]
layout = base.slide_layout


def rgb(h):
    return RGBColor.from_string(h)


def new_slide(title, notes):
    slide = prs.slides.add_slide(layout)
    for ph in list(slide.placeholders):
        ph._element.getparent().remove(ph._element)
    for sh in base.shapes:
        if sh.name in ("Title 1", "Slide Number Placeholder 1"):
            slide.shapes._spTree.append(copy.deepcopy(sh._element))
    for sh in slide.shapes:
        if sh.name == "Title 1":
            runs = sh.text_frame.paragraphs[0].runs
            runs[0].text = title
            for extra in runs[1:]:
                extra._r.getparent().remove(extra._r)
    slide.notes_slide.notes_text_frame.text = notes
    return slide


class Canvas:
    def __init__(self, slide):
        self.s = slide

    def box(self, x, y, w, h, fill, *, line=None, dash=False, radius=5000, name="Box"):
        sh = self.s.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)
        )
        sh.name = name
        sh.adjustments[0] = radius / 100000
        sh.shadow.inherit = False
        if fill is None:
            sh.fill.background()
        else:
            sh.fill.solid()
            sh.fill.fore_color.rgb = rgb(fill)
        if line:
            sh.line.color.rgb = rgb(line)
            sh.line.width = Pt(1.25)
            if dash:
                etree.SubElement(sh.line._get_or_add_ln(), qn("a:prstDash")).set("val", "dash")
        else:
            sh.line.fill.background()
        sh.text_frame.text = ""
        return sh

    def text(self, x, y, w, h, paras, *, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT, name="Text"):
        """paras: list of (string, size, bold, colour) or (..., space_after_pt)."""
        tb = self.s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tb.name = name
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = anchor
        for i, para in enumerate(paras):
            s, size, bold, colour = para[:4]
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            if len(para) > 4:
                p.space_after = Pt(para[4])
            r = p.add_run()
            r.text = s
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.name = "Calibri"
            r.font.color.rgb = rgb(colour)
        return tb

    def lead(self, s):
        self.text(0.5, 1.02, 9.0, 0.6, [(s, 15, False, MUTED)], name="Lead-in")

    def foot(self, s, y=6.45):
        self.text(0.5, y, 9.0, 0.35, [(s, 10.5, False, MUTED)], name="Footnote")

    def stat(self, x, y, w, h, big, small, fill=GREY, big_size=38, small_size=14):
        self.box(x, y, w, h, fill, name="Stat")
        self.text(
            x + 0.2,
            y + 0.18,
            w - 0.4,
            h - 0.3,
            [(big, big_size, True, RED, 4), (small, small_size, False, INK)],
            name="Stat text",
        )

    def arrow(self, x1, y1, x2, y2, dashed=False):
        c = self.s.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
        )
        c.line.color.rgb = rgb(MUTED)
        c.line.width = Pt(1.75)
        ln = c.line._get_or_add_ln()
        if dashed:
            etree.SubElement(ln, qn("a:prstDash")).set("val", "dash")
        etree.SubElement(ln, qn("a:tailEnd")).set("type", "triangle")

    def badge(self, x, y, d, label):
        b = self.s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
        b.shadow.inherit = False
        b.fill.solid()
        b.fill.fore_color.rgb = rgb(RED)
        b.line.fill.background()
        tf = b.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = label
        r.font.size = Pt(15)
        r.font.bold = True
        r.font.name = "Calibri"
        r.font.color.rgb = rgb("FFFFFF")


def set_lines(shape, lines):
    """Replace the text of a title-slide shape, keeping the first paragraph's formatting."""
    paras = shape.text_frame.paragraphs
    first = paras[0]
    for extra in paras[1:]:
        extra._p.getparent().remove(extra._p)
    for r in first.runs[1:]:
        r._r.getparent().remove(r._r)
    first.runs[0].text = lines[0]
    for line in lines[1:]:
        clone = copy.deepcopy(first._p)
        first._p.getparent().append(clone)
        for t in clone.iter(qn("a:t")):
            t.text = line


# ---------------------------------------------------------------- slide 1: title (reuse)
title_slide = prs.slides[0]
boxes = [sh for sh in title_slide.shapes if sh.name == "Title 6"]
set_lines(boxes[0], ["Gợi ý câu hỏi trùng trên Stack Overflow"])
set_lines(
    boxes[1],
    [
        "Thêm comment có giúp gợi ý tốt hơn không?",
        "Báo cáo tiến độ phần dữ liệu: làm sạch và EDA",
        "Nhập môn Khoa học dữ liệu · IT4142E",
    ],
)
title_slide.notes_slide.notes_text_frame.text = (
    "Mở đầu: nhóm đang làm một hệ thống gợi ý câu hỏi trên Stack Overflow. Hôm nay mình báo cáo phần dữ liệu: "
    "lấy dữ liệu ở đâu, làm sạch thế nào, và EDA cho thấy gì. Vì không phải ai cũng nắm đề tài, "
    "mình sẽ giải thích bài toán trước, rồi mới vào dữ liệu."
)

# ---------------------------------------------------------------- slide 2: the problem
s = new_slide(
    "Vấn đề: câu hỏi của bạn có thể đã có người hỏi",
    "Stack Overflow là trang hỏi đáp lập trình lớn nhất, có hơn 24 triệu câu hỏi. Rất nhiều câu mới thực ra đã được hỏi và có "
    "câu trả lời từ trước. Khi đó người kiểm duyệt đóng câu mới với lý do duplicate (trùng) và gắn link tới câu gốc. "
    "Ví dụ thật: câu 1781571 hỏi cách nối hai dictionary, bị đóng vì trùng với câu 38987, một câu kinh điển có 7.129 điểm "
    "và 453 câu khác trỏ về. Người hỏi đã mất công đặt câu mới trong khi câu trả lời có sẵn. Ý tưởng của đề tài: khi ai đó "
    "đặt câu hỏi, hệ thống gợi ý ngay những câu có sẵn liên quan nhất. Ví dụ trích từ Stack Overflow (giấy phép CC BY-SA).",
)
c = Canvas(s)
ex_new, ex_old = N["example"]["1781571"], N["example"]["38987"]
c.lead(
    f"Stack Overflow có hơn {N['site_total_questions'] // 1_000_000} triệu câu hỏi. Rất nhiều câu mới thực ra đã được hỏi và trả lời từ trước."
)
c.box(0.5, 1.95, 3.95, 2.75, AMBER)
c.text(
    0.72,
    1.95,
    3.5,
    2.75,
    [
        ("CÂU HỎI MỚI", 12, True, RED, 6),
        (ex_new["title"], 18, True, INK, 8),
        (f"{ex_new['score']} điểm", 13, False, MUTED, 2),
        ("Bị đóng với lý do: Duplicate (trùng)", 13, False, MUTED),
    ],
    anchor=MSO_ANCHOR.MIDDLE,
)
c.arrow(4.5, 3.3, 5.55, 3.3)
c.text(4.48, 2.95, 1.1, 0.3, [("trỏ tới", 12, False, MUTED)], align=PP_ALIGN.CENTER)
c.box(5.55, 1.95, 3.95, 2.75, GREY)
c.text(
    5.77,
    1.95,
    3.5,
    2.75,
    [
        ("CÂU GỐC ĐÃ CÓ SẴN", 12, True, RED, 6),
        (ex_old["title"], 18, True, INK, 8),
        (f"{vn(ex_old['score'])} điểm", 13, False, MUTED, 2),
        (f"{N['example_links_to_38987']} câu khác trỏ về câu này", 13, False, MUTED),
    ],
    anchor=MSO_ANCHOR.MIDDLE,
)
c.box(0.5, 5.0, 9.0, 1.2, AMBER, line=RED)
c.text(
    0.8,
    5.0,
    8.4,
    1.2,
    [
        (
            "Ý tưởng: khi ai đó đặt câu hỏi, hệ thống gợi ý ngay K câu có sẵn liên quan nhất để họ tìm được câu trả lời mà không phải chờ.",
            16,
            True,
            RED,
        )
    ],
    anchor=MSO_ANCHOR.MIDDLE,
)
c.foot("Ví dụ lấy từ Stack Overflow (CC BY-SA), số liệu qua API chính thức ngày 12/11/2026.")

# ---------------------------------------------------------------- slide 3: the topic
s = new_slide(
    "Đề tài và câu hỏi nghiên cứu",
    "Đề tài là bài toán xếp hạng: đầu vào là một câu hỏi, đầu ra là K câu hỏi có sẵn liên quan nhất, K ví dụ bằng 5. "
    "Câu hỏi nghiên cứu của nhóm là: thêm comment dưới câu hỏi có giúp gợi ý đúng hơn không. Để trả lời, nhóm so sánh hai cách "
    "biểu diễn một câu hỏi bằng văn bản. Cách C chỉ dùng tiêu đề và nội dung. Cách C cộng Cm dùng thêm comment. Mọi thứ khác "
    "giữ nguyên, chỉ đổi văn bản đầu vào nên so sánh công bằng. Comment có thể có ích, ví dụ chứa thông báo lỗi hay phiên bản "
    "thư viện, nhưng cũng có thể chỉ là cảm ơn nên gây nhiễu. Đó là lý do câu hỏi này đáng thử.",
)
c = Canvas(s)
c.lead("Hệ thống nhận một câu hỏi và trả về danh sách K câu có sẵn liên quan nhất.")
for x, w, title, body, fill in (
    (0.5, 2.6, "Câu hỏi đầu vào", "Một câu hỏi người dùng vừa đặt", AMBER),
    (3.75, 2.5, "Hệ thống gợi ý", "So sánh với các câu hỏi có sẵn", GREY),
    (6.9, 2.6, "Top-K câu liên quan", "Xếp từ liên quan nhất, K ví dụ là 5", AMBER),
):
    c.box(x, 1.75, w, 1.3, fill)
    c.text(
        x + 0.15,
        1.75,
        w - 0.3,
        1.3,
        [(title, 16, True, RED, 3), (body, 13, False, INK)],
        anchor=MSO_ANCHOR.MIDDLE,
        align=PP_ALIGN.CENTER,
    )
c.arrow(3.1, 2.4, 3.75, 2.4)
c.arrow(6.25, 2.4, 6.9, 2.4)
c.text(
    0.5,
    3.35,
    9.0,
    0.5,
    [("Câu hỏi nghiên cứu: thêm comment có giúp gợi ý đúng hơn không?", 18, True, RED)],
)
c.box(0.5, 3.95, 4.4, 1.55, GREY)
c.text(
    0.7,
    3.95,
    4.0,
    1.55,
    [("Cách C", 17, True, RED, 3), ("Tiêu đề + nội dung câu hỏi", 15, False, INK)],
    anchor=MSO_ANCHOR.MIDDLE,
)
c.box(5.1, 3.95, 4.4, 1.55, AMBER)
c.text(
    5.3,
    3.95,
    4.0,
    1.55,
    [
        ("Cách C + Cm", 17, True, RED, 3),
        ("Tiêu đề + nội dung + comment dưới câu hỏi", 15, False, INK),
    ],
    anchor=MSO_ANCHOR.MIDDLE,
)
c.text(
    0.5,
    5.75,
    9.0,
    0.8,
    [
        (
            'Cùng một mô hình, cùng tham số, chỉ đổi văn bản đầu vào. Comment có thể có ích (thông báo lỗi, phiên bản) hoặc chỉ là nhiễu ("thanks").',
            14,
            False,
            MUTED,
        )
    ],
)

# ---------------------------------------------------------------- slide 4: whole project
s = new_slide(
    "Toàn bộ dự án và chỗ chúng ta đang đứng",
    "Dự án đi từ trái sang phải. Thu thập: gọi API chính thức của Stack Exchange và lưu dữ liệu thô. Làm sạch: dùng PySpark "
    "để bóc HTML, lọc và ghép các bảng. EDA: xem dữ liệu để tìm vấn đề và phát hiện. Hai bước cuối là mô hình và đánh giá, do "
    "bên model phụ trách. Báo cáo hôm nay nói về ba bước đầu. Quy tắc quan trọng: mỗi bước chỉ đọc kết quả bước trước, "
    "và dữ liệu thô không bao giờ bị sửa.",
)
c = Canvas(s)
c.lead("Mỗi bước đọc kết quả của bước trước. Báo cáo hôm nay nói về ba bước đầu.")
steps = [
    ("Thu thập", "Gọi API Stack Exchange, lưu dữ liệu thô", "Xong", GREY, False),
    ("Làm sạch", "PySpark: bóc HTML, lọc, ghép bảng", "Đã chốt luật, đang kiểm tra", AMBER, False),
    ("EDA", "Xem dữ liệu, tìm vấn đề và phát hiện", "Đang cập nhật", AMBER, False),
    ("Mô hình", "Biểu diễn câu hỏi và xếp hạng", "Bên model", WHITE, True),
    ("Đánh giá", "Đo chất lượng, viết báo cáo", "Sau", WHITE, True),
]
xs = [0.5 + i * 1.875 for i in range(5)]
c.box(0.5, 1.75, 5.25, 0.12, RED, radius=50000)
c.text(0.5, 1.4, 5.3, 0.3, [("Phần báo cáo hôm nay", 12, True, RED)])
for i, (title, body, status, fill, planned) in enumerate(steps):
    x = xs[i]
    c.box(x, 2.1, 1.5, 2.6, fill, line=LINE if planned else None, dash=planned)
    c.text(
        x + 0.12,
        2.2,
        1.26,
        2.45,
        [(title, 16, True, RED, 5), (body, 12.5, False, INK, 8), (status, 12, True, MUTED)],
    )
    if i < 4:
        c.arrow(x + 1.5, 3.4, x + 1.875, 3.4)
for i, (label, fill, planned) in enumerate(
    (("Xong", GREY, False), ("Đang làm", AMBER, False), ("Chưa tới / bên khác", WHITE, True))
):
    x = 0.5 + i * 2.1
    c.box(x, 5.0, 0.26, 0.22, fill, line=LINE if planned else None, dash=planned, radius=15000)
    c.text(x + 0.36, 4.98, 1.7, 0.26, [(label, 12, False, MUTED)], anchor=MSO_ANCHOR.MIDDLE)
c.box(0.5, 5.55, 9.0, 0.95, GREY)
c.text(
    0.75,
    5.55,
    8.5,
    0.95,
    [
        (
            "Dữ liệu thô không bao giờ bị sửa. Mọi bước làm sạch đọc từ thư mục thô và ghi sang thư mục sạch.",
            15,
            True,
            INK,
        )
    ],
    anchor=MSO_ANCHOR.MIDDLE,
)

# ---------------------------------------------------------------- slide 5: data source
s = new_slide(
    "Dữ liệu lấy từ đâu",
    "Dữ liệu chỉ lấy qua API chính thức của Stack Exchange, không scrape và không vượt cơ chế chống bot. Chiến lược lấy mẫu "
    "có bốn bước: seed là 10.000 câu có tag python được vote cao nhất, thường là các câu kinh điển có nhiều câu khác trùng với nó; "
    "tiếp theo là các câu hỏi có link tới seed, nơi có nhiều câu bị đóng vì trùng; rồi các câu gốc còn thiếu; cuối cùng là câu trả "
    f"lời và comment. Một điểm cần nhớ: tag python có {vn(N['python_tag_total'])} câu hỏi, nhóm chỉ có {vn(N['q_with_python_tag'])} câu, "
    f"khoảng {pct(N['q_with_python_tag'] / N['python_tag_total'])}. Và {pct(N['q_only_linked_share'], 0)} câu chỉ vào dữ liệu qua đường link tới seed, "
    "nên đây không phải mẫu ngẫu nhiên. Lý do chọn cách này: câu trùng vốn hay trỏ tới câu gốc nổi tiếng, nên cách lấy mẫu cho nhiều cặp trùng với ít request.",
)
c = Canvas(s)
c.lead("Chỉ dùng API chính thức của Stack Exchange, không scrape, không vượt chống bot.")
for i, (title, body) in enumerate(
    (
        ("Seed", "10.000 câu tag python có vote cao nhất, thường là câu kinh điển"),
        ("Câu liên kết", "Các câu có link tới seed, nhiều câu bị đóng vì trùng nằm ở đây"),
        ("Câu gốc bổ sung", "Câu gốc mà hai bước trên bỏ sót, lấy theo ID"),
        ("Trả lời và comment", "Của mọi câu hỏi đã lấy"),
    )
):
    y = 1.65 + i * 1.07
    c.box(0.5, y, 5.7, 0.95, GREY)
    c.badge(0.68, y + 0.205, 0.54, str(i + 1))
    c.text(1.42, y, 1.75, 0.95, [(title, 16, True, RED)], anchor=MSO_ANCHOR.MIDDLE)
    c.text(3.2, y, 2.9, 0.95, [(body, 13, False, INK)], anchor=MSO_ANCHOR.MIDDLE)
c.stat(
    6.45,
    1.7,
    3.05,
    2.35,
    pct(N["q_with_python_tag"] / N["python_tag_total"]),
    f"số câu tag python của Stack Overflow mà nhóm có ({vn(N['q_with_python_tag'])} trên {vn(N['python_tag_total'])})",
    fill=AMBER,
    big_size=40,
    small_size=13.5,
)
c.stat(
    6.45,
    4.25,
    3.05,
    1.65,
    pct(N["q_only_linked_share"], 0),
    "câu hỏi chỉ vào dữ liệu qua link tới seed",
    big_size=36,
    small_size=13.5,
)
c.foot(
    "Số liệu: API Stack Exchange ngày 12/11/2026. Đây không phải mẫu ngẫu nhiên, xem slide Giới hạn.",
    y=6.3,
)

# ---------------------------------------------------------------- slide 6: problems in the raw data
leaky = N["c_leaky"]
s = new_slide(
    "Dữ liệu thô có những vấn đề gì",
    "Dữ liệu API trả về không dùng thẳng được. Sáu vấn đề chính. Một: mỗi câu hỏi xuất hiện trung bình 2,9 lần, nên phải khử trùng. "
    "Hai: nội dung là HTML, lẫn thẻ và khối code. Ba: có hơn 15 nghìn comment lộ đáp án, ví dụ Possible duplicate of, tức là chính "
    "comment cho biết câu gốc. Bốn: nhiều comment dẫn link thẳng tới câu gốc, và với "
    + pct(_leak_share()).replace("%", " phần trăm")
    + " câu trùng thì comment trỏ "
    "đúng câu gốc của nó, nên nếu giữ nguyên thì cấu hình C cộng Cm sẽ chứa sẵn đáp án. Năm: API báo có comment nhưng không lấy được "
    "ở 935 câu hỏi. Sáu: có 20 cặp câu đăng lại y hệt. Vấn đề ba và bốn quan trọng nhất vì chúng làm hỏng phép so sánh của đề tài.",
)
c = Canvas(s)
c.lead("Dữ liệu API trả về không dùng thẳng được. Sáu vấn đề chính:")
cards = [
    (
        "2,9 lần",
        f"mỗi câu hỏi xuất hiện trung bình 2,9 lần ({vn(N['q_raw_records'])} bản ghi cho {vn(N['q_unique'])} câu)",
        GREY,
    ),
    ("HTML", "tiêu đề có ký tự mã hóa, nội dung có thẻ HTML lẫn khối code", GREY),
    (vn(leaky), 'comment lộ đáp án, như "Possible duplicate of…"', GREY),
    (pct(_leak_share()), "câu trùng có comment dẫn link thẳng tới câu gốc của nó", AMBER),
    ("935", "câu hỏi mà API báo có comment nhưng không lấy được comment nào", AMBER),
    ("20", "cặp câu hỏi đăng lại y hệt, bản đăng trước luôn 0 câu trả lời", AMBER),
]
for i, (big, small, fill) in enumerate(cards):
    c.stat(
        0.5 + (i % 3) * 3.05,
        1.75 + (i // 3) * 2.3,
        2.9,
        2.1,
        big,
        small,
        fill=fill,
        big_size=34,
        small_size=13.5,
    )
c.foot("Số liệu: lần chạy làm sạch ngày 13/11/2026 và thống kê dữ liệu thô.", y=6.45)

# ---------------------------------------------------------------- slide 7: cleaning flow
s = new_slide(
    "Quy trình làm sạch",
    "Pipeline viết bằng PySpark, chạy trong Docker. Bước một: khử trùng, giữ bản lấy về mới nhất của mỗi ID, từ 272 nghìn bản ghi "
    "còn 93.704 câu hỏi. Bước hai: chuẩn hóa từng trường, bóc HTML, tách code ra riêng, đổi ngày, chuẩn hóa tag, và thay các link "
    "sang câu hỏi khác bằng chữ link. Bước ba: lọc câu hỏi, loại 286 câu điểm từ âm 5 trở xuống và 19 bản đăng lại y hệt. Bước bốn: "
    "lọc comment, loại comment lộ đáp án, comment chỉ có link và comment lặp. Bước năm: bỏ câu trả lời và comment của những câu đã "
    "bị loại, rồi đếm lại số comment vì API đếm không chuẩn. Kết quả cuối là 93.399 câu hỏi, 257.436 câu trả lời, 627.669 comment. "
    "Mỗi bước ghi số dòng vào, ra, bị loại và lý do, nên báo cáo có số liệu cho từng bước.",
)
c = Canvas(s)
c.lead("Mỗi bước đọc kết quả bước trước và ghi số dòng vào, ra, bị loại.")
rows = [
    (
        "Khử trùng",
        f"{vn(N['q_raw_records'])} bản ghi câu hỏi còn {vn(N['q_unique'])}, giữ bản lấy về mới nhất",
    ),
    ("Chuẩn hóa", "Bóc HTML, tách code, đổi ngày và tag, thay link sang câu khác bằng [link]"),
    (
        "Lọc câu hỏi",
        f"Loại {N['q_quality_reasons']['SCORE_TOO_LOW']} câu điểm ≤ −5 và {N['q_quality_reasons']['DUPLICATE_TEXT']} bản đăng lại y hệt",
    ),
    (
        "Lọc comment",
        f"Loại {vn(N['c_leaky'])} comment lộ đáp án, {vn(N['c_only_link'])} chỉ có link, {N['c_repeats']} lặp",
    ),
    (
        "Bỏ mồ côi, đếm lại",
        f"Bỏ {N['a_orphans']} câu trả lời và {vn(N['c_orphans'])} comment của câu đã bị loại; đếm lại số comment",
    ),
]
for i, (title, body) in enumerate(rows):
    y = 1.5 + i * 0.74
    c.box(0.5, y, 9.0, 0.66, GREY)
    c.badge(0.65, y + 0.06, 0.54, str(i + 1))
    c.text(1.4, y, 2.2, 0.66, [(title, 15, True, RED)], anchor=MSO_ANCHOR.MIDDLE)
    c.text(3.6, y, 5.8, 0.66, [(body, 13, False, INK)], anchor=MSO_ANCHOR.MIDDLE)
for i, (big, small) in enumerate(
    (
        (vn(N["q_clean"]), "câu hỏi"),
        (vn(N["a_clean"]), "câu trả lời"),
        (vn(N["c_clean"]), "comment"),
    )
):
    c.stat(0.5 + i * 3.05, 5.35, 2.9, 0.95, big, small, fill=AMBER, big_size=26, small_size=13)
c.foot(
    "Dữ liệu thô không bị sửa · bảng rejected giữ mọi dòng bị loại kèm lý do · Spark chạy trong Docker.",
    y=6.55,
)

# ---------------------------------------------------------------- slide 8: decisions
# closed for another reason: all the score groups the quality rule drops, against score >= 0
dropped = [g for g in N["score_profile"] if g.get("dropped")]
low = sum(g["closed_other_share"] * g["questions"] for g in dropped) / sum(
    g["questions"] for g in dropped
)
high = next(g for g in N["score_profile"] if g["score_group"] == ">= 0")["closed_other_share"]
s = new_slide(
    "Các quyết định làm sạch và bằng chứng",
    "Điểm khác biệt của phần làm sạch là mỗi luật lọc đều dựa trên số liệu thật, không đặt ngưỡng cảm tính. "
    f"Một: loại câu điểm từ âm 5 trở xuống, vì nhóm này bị đóng vì lý do khác nhiều gấp khoảng 20 lần, {pct(low)} so với {pct(high)}. "
    "Hai: thay link sang câu hỏi khác bằng chữ link, vì "
    + pct(_leak_share()).replace("%", " phần trăm")
    + " câu trùng có comment trỏ thẳng tới câu gốc. "
    "Ba: với 20 cặp câu đăng lại y hệt, giữ bản có câu trả lời thay vì bản đăng trước, vì bản đăng trước luôn không có câu trả lời. "
    "Bốn: comment ít thông tin được gắn nhãn thay vì xóa, vì xóa là tự quyết kết quả của thí nghiệm về comment. "
    "Năm: không lọc theo ngôn ngữ hay độ dài, vì đọc mẫu thấy chúng là câu hỏi hợp lệ. Mỗi quyết định được ghi ở mục D14 trong tài liệu.",
)
c = Canvas(s)
c.lead("Mỗi luật lọc đều dựa trên số liệu thật. Năm quyết định chính:")
c.text(0.7, 1.55, 3.4, 0.3, [("QUYẾT ĐỊNH", 11.5, True, MUTED)])
c.text(4.4, 1.55, 5.0, 0.3, [("BẰNG CHỨNG", 11.5, True, MUTED)])
rows = [
    (
        f"Loại câu hỏi điểm ≤ −5 ({N['q_quality_reasons']['SCORE_TOO_LOW']} câu)",
        f"Nhóm này bị đóng vì lý do khác nhiều gấp khoảng 20 lần: {pct(low)} so với {pct(high)}",
    ),
    (
        "Thay link sang câu khác bằng [link]",
        pct(_leak_share())
        + " câu trùng có comment dẫn thẳng tới câu gốc, nên C+Cm sẽ chứa sẵn đáp án",
    ),
    (
        "Bản đăng lại y hệt: giữ bản tốt hơn",
        "20 cặp đều do người hỏi đăng lại; bản đăng trước luôn có 0 câu trả lời",
    ),
    (
        f"Comment ít thông tin: gắn nhãn, không xóa ({vn(N['c_low_info'])})",
        "Xóa là can thiệp vào thí nghiệm về comment; gắn nhãn để người dùng tự chọn",
    ),
    (
        "Không lọc theo ngôn ngữ và độ dài",
        "Đọc mẫu: chữ nước ngoài chỉ là ví dụ trong câu hỏi tiếng Anh; câu ngắn vẫn hợp lệ",
    ),
]
for i, (left, right) in enumerate(rows):
    y = 1.9 + i * 0.9
    c.box(0.5, y, 9.0, 0.8, GREY if i % 2 == 0 else AMBER)
    c.text(0.7, y, 3.5, 0.8, [(left, 14, True, RED)], anchor=MSO_ANCHOR.MIDDLE)
    c.text(4.4, y, 5.0, 0.8, [(right, 13, False, INK)], anchor=MSO_ANCHOR.MIDDLE)

# ---------------------------------------------------------------- slide 9: the clean data
s = new_slide(
    "Kết quả: dữ liệu sạch",
    "Sau làm sạch, nhóm có năm bảng dữ liệu, lưu dạng Parquet. Bảng questions chứa câu hỏi với tiêu đề, nội dung dạng chữ, "
    "code tách riêng, tag, điểm, lượt xem, ngày đăng và lý do đóng. Bảng answers và comments tương tự, comments có thêm nhãn ít "
    "thông tin. File documents gom mỗi câu hỏi thành một dòng gồm tiêu đề, nội dung, danh sách comment và tag, đây là định dạng "
    "bên model yêu cầu, có cả JSON và Parquet. Bảng rejected giữ lại các dòng bị loại kèm lý do để kiểm tra lại sau.",
)
c = Canvas(s)
c.lead("Năm bảng, lưu dạng Parquet trong thư mục data/clean.")
for i, (big, small) in enumerate(
    (
        (vn(N["q_clean"]), "câu hỏi"),
        (vn(N["a_clean"]), "câu trả lời"),
        (vn(N["c_clean"]), "comment"),
    )
):
    c.stat(0.5 + i * 3.05, 1.65, 2.9, 1.65, big, small, big_size=34, small_size=15)
tables = [
    ("questions", "tiêu đề, nội dung, code, tag, điểm, lượt xem, ngày đăng, lý do đóng"),
    ("answers", "câu trả lời, có nhãn được chấp nhận"),
    ("comments", "comment của câu hỏi và câu trả lời, có nhãn ít thông tin"),
    ("documents", "mỗi câu hỏi một dòng: tiêu đề, nội dung, comment, tag (JSON và Parquet)"),
    ("rejected", "các dòng bị loại kèm lý do, để kiểm tra lại"),
]
for i, (name, body) in enumerate(tables):
    y = 3.55 + i * 0.6
    c.box(0.5, y, 9.0, 0.52, GREY if i % 2 == 0 else AMBER)
    c.text(0.7, y, 1.8, 0.52, [(name, 14, True, RED)], anchor=MSO_ANCHOR.MIDDLE)
    c.text(2.5, y, 6.9, 0.52, [(body, 13, False, INK)], anchor=MSO_ANCHOR.MIDDLE)

# ---------------------------------------------------------------- slide 10: EDA findings
rho = N["spearman_comment_count"]
rho_lo, rho_hi = (
    f"−{abs(v):.2f}".replace(".", ",") for v in (max(rho.values()), min(rho.values()))
)
no_comment = 1 - N["q_with_comments_share"]
s = new_slide(
    "EDA: ba điều đáng chú ý",
    "EDA là bước nhìn kỹ dữ liệu để hiểu nó và tìm ra vấn đề, trước khi làm mô hình. Ba phát hiện đáng chú ý. Một: điểm của câu hỏi "
    f"lệch rất mạnh, trung vị chỉ là 1 nhưng trung bình là {str(N['score_mean']).replace('.', ',')} vì có vài câu cực nổi tiếng, một câu có {vn(N['score_max'])} điểm. "
    "Vì vậy khi mô tả phải dùng trung vị, không dùng trung bình. Hai: khoảng một phần tư câu hỏi không có comment nào, nên với những "
    "câu đó cách C và C cộng Cm giống hệt nhau, khi đánh giá nên tách riêng nhóm câu có comment. Ba: số comment gần như không liên quan "
    "tới điểm hay lượt xem, tương quan Spearman chỉ từ âm 0,06 đến âm 0,09. Nghĩa là comment không phải thước đo độ nổi tiếng mà là một tín hiệu riêng, đáng thử đưa vào mô hình.",
)
c = Canvas(s)
c.lead("Tính trên dữ liệu sạch ngày 13/11/2026.")
cards = [
    (
        f"Trung vị {int(N['score_median'])}\ntrung bình {str(N['score_mean']).replace('.', ',')}",
        "Điểm câu hỏi lệch rất mạnh",
        f"Một câu có {vn(N['score_max'])} điểm. Phải dùng trung vị và thang log, không dùng trung bình.",
        GREY,
    ),
    (
        pct(no_comment),
        "câu hỏi không có comment",
        "Với các câu này, C và C+Cm giống hệt nhau. Khi đánh giá nên tách riêng nhóm có comment.",
        AMBER,
    ),
    (
        "|ρ| ≤ 0,09",
        "Số comment không đi theo độ nổi tiếng",
        f"Tương quan với điểm, lượt xem, số câu trả lời chỉ từ {rho_lo} đến {rho_hi}. Comment là tín hiệu riêng, đáng thử.",
        GREY,
    ),
]
for i, (big, head, body, fill) in enumerate(cards):
    x = 0.5 + i * 3.05
    c.box(x, 1.6, 2.9, 3.75, fill)
    paras = [(line, 28 if "\n" in big else 36, True, RED, 2) for line in big.split("\n")]
    paras[-1] = paras[-1][:4] + (10,)
    paras += [(head, 16, True, INK, 8), (body, 13.5, False, INK)]
    c.text(x + 0.2, 1.8, 2.5, 3.4, paras)
c.box(0.5, 5.55, 9.0, 0.8, AMBER, line=RED)
c.text(
    0.8,
    5.55,
    8.4,
    0.8,
    [
        (
            "Hệ quả: mô tả bằng trung vị, tách riêng nhóm câu có comment, và thử comment như một tín hiệu riêng.",
            14.5,
            True,
            RED,
        )
    ],
    anchor=MSO_ANCHOR.MIDDLE,
)
c.foot(
    "ρ: hệ số tương quan hạng Spearman, bền với dữ liệu lệch. Chi tiết và biểu đồ nằm trong reports/eda.",
    y=6.5,
)

# ---------------------------------------------------------------- slide 11: limits (native chart)
years = {int(k): v for k, v in N["by_year"].items()}
s = new_slide(
    "Giới hạn của dữ liệu",
    "Điều quan trọng cần nói thẳng: dữ liệu là một mẫu nhỏ và không ngẫu nhiên. Tag python có 2,2 triệu câu hỏi, nhóm có khoảng 3,7 phần trăm. "
    "Và 87 phần trăm câu hỏi chỉ vào dữ liệu vì chúng có link tới một câu seed nổi tiếng. Hệ quả: số câu theo năm trong biểu đồ phản ánh một phần "
    "cách thu thập, không chỉ là hoạt động thật của Stack Overflow, ví dụ gần như mọi câu từ 2018 trở đi vào mẫu qua đường link. 56 phần trăm "
    "câu hỏi nằm trong giai đoạn 2018 đến 2022. Ngoài ra khoảng 13 phần trăm câu không có tag python, vì chúng chỉ trỏ tới một câu python. "
    "Khi viết báo cáo cần nói mẫu này, đừng nói Stack Overflow nói chung. Phương án cải thiện khi crawl thêm: lấy thêm một phần mẫu ngẫu nhiên các câu python để so sánh.",
)
c = Canvas(s)
c.lead("Dữ liệu là một mẫu nhỏ, không ngẫu nhiên. Cần đọc kết quả với giới hạn này.")
cd = CategoryChartData()
yrs = sorted(years)
cd.categories = [str(y) for y in yrs]
cd.add_series("Số câu hỏi", [years[y] for y in yrs])
gf = s.shapes.add_chart(
    XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.4), Inches(1.6), Inches(5.6), Inches(4.3), cd
)
chart = gf.chart
chart.has_legend = False
chart.has_title = False
plot = chart.plots[0]
plot.gap_width = 40
ser = plot.series[0]
for idx, y in enumerate(yrs):
    pt = ser.points[idx]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = rgb(RED if 2018 <= y <= 2022 else "BFBFBF")
cat, val = chart.category_axis, chart.value_axis
cat.tick_labels.font.size = Pt(10)
cat.tick_labels.font.name = "Calibri"
val.tick_labels.font.size = Pt(10)
val.tick_labels.font.name = "Calibri"
val.tick_labels.number_format = "#,##0"
val.tick_labels.number_format_is_linked = False
val.major_gridlines.format.line.color.rgb = rgb("E3E3E3")
val.format.line.fill.background()
cat.format.line.color.rgb = rgb(LINE)
c.text(
    0.5,
    5.95,
    5.5,
    0.5,
    [
        (
            f"Số câu hỏi theo năm đăng. {pct(N['share_2018_2022'], 0)} nằm trong 2018–2022 (cột đỏ). 2026 chỉ tới 24/10.",
            11.5,
            False,
            MUTED,
        )
    ],
)
for i, (big, small) in enumerate(
    (
        (
            pct(N["q_with_python_tag"] / N["python_tag_total"]),
            "câu tag python của Stack Overflow nằm trong mẫu",
        ),
        (
            pct(N["q_only_linked_share"], 0),
            "câu vào mẫu qua link tới seed, nên số câu theo năm phản ánh một phần cách thu thập",
        ),
        (pct(1 - N["q_python_share"]), "câu không có tag python: chúng chỉ trỏ tới một câu python"),
    )
):
    c.stat(
        6.2,
        1.55 + i * 1.62,
        3.3,
        1.52,
        big,
        small,
        fill=AMBER if i == 1 else GREY,
        big_size=28,
        small_size=12,
    )
c.foot('Hệ quả: khi viết báo cáo, nói "mẫu này", không nói "Stack Overflow nói chung".', y=6.55)

# ---------------------------------------------------------------- slide 12: status + decisions
s = new_slide(
    "Tiến độ và những việc cần bàn",
    "Đã xong: thu thập hơn 93 nghìn câu hỏi cùng câu trả lời và comment; pipeline làm sạch trên PySpark có test tự động; mỗi luật lọc "
    "đều có bằng chứng; bộ dữ liệu sạch ở dạng Parquet và JSON. Đang làm: kiểm tra bảng rejected xem có dòng nào bị loại nhầm do lỗi "
    "trong luật làm sạch không, cập nhật báo cáo EDA, và xuất lại dữ liệu cho bên model. Cần nhóm bàn ba việc. Một: nhãn để đánh giá. "
    "Cặp câu trùng và câu gốc không còn nằm trong dữ liệu sạch, vì phần làm sạch không tạo cặp nữa. Cần thống nhất ai tạo nhãn đó và ở đâu, "
    "vì nhãn này là cơ sở để đo mô hình. Hai: dùng JSON hay Parquet. Ba: crawl thêm thì có lấy thêm một phần mẫu ngẫu nhiên không.",
)
c = Canvas(s)
panels = [
    (
        "Đã xong",
        GREY,
        [
            f"Thu thập {N['q_unique'] // 1000} nghìn câu hỏi kèm câu trả lời và comment",
            "Pipeline làm sạch PySpark, có test tự động",
            "Mỗi luật lọc có bằng chứng",
            "Dữ liệu sạch dạng Parquet và JSON",
        ],
    ),
    (
        "Đang làm",
        AMBER,
        [
            "Kiểm tra bảng rejected xem có dòng bị loại nhầm không",
            "Cập nhật báo cáo EDA theo dữ liệu mới",
            "Xuất lại dữ liệu cho bên model",
        ],
    ),
    (
        "Cần nhóm bàn",
        GREY,
        [
            "Nhãn để đánh giá: cặp câu trùng không còn trong dữ liệu sạch. Ai tạo, ở đâu?",
            "Dùng JSON hay Parquet",
            "Crawl thêm: có lấy mẫu ngẫu nhiên không?",
        ],
    ),
]
for i, (head, fill, items) in enumerate(panels):
    x = 0.5 + i * 3.05
    c.box(x, 1.15, 2.9, 4.6, fill, line=RED if i == 2 else None)
    paras = [(head, 20, True, RED, 12)] + [("• " + it, 15.5, False, INK, 10) for it in items]
    c.text(x + 0.22, 1.35, 2.5, 4.2, paras)
c.box(0.5, 5.95, 9.0, 0.8, AMBER, line=RED)
c.text(
    0.8,
    5.95,
    8.4,
    0.8,
    [("Cần từ nhóm hôm nay: thống nhất nhãn đánh giá và định dạng file dữ liệu.", 15, True, RED)],
    anchor=MSO_ANCHOR.MIDDLE,
)

# ---------------------------------------------------------------- slide 13: thanks (reuse the last slide)
thanks = prs.slides[7]
for sh in thanks.shapes:
    if sh.name == "Title 10":
        set_lines(sh, ["CẢM ƠN CÁC BẠN!"])
thanks.notes_slide.notes_text_frame.text = (
    "Kết thúc. Mời cả nhóm hỏi đáp, và cho ý kiến về ba việc cần bàn ở slide trước."
)

# ---------------------------------------------------------------- order: title, new slides, thanks
ids = prs.slides._sldIdLst
all_ids = list(ids)
title_id, thanks_id = all_ids[0], all_ids[7]
old_middle = all_ids[1:7]
new_ids = all_ids[8:]
for sld in old_middle:
    prs.part.drop_rel(sld.rId)
    ids.remove(sld)
for sld in (title_id, thanks_id, *new_ids):
    ids.remove(sld)
for sld in (title_id, *new_ids, thanks_id):
    ids.append(sld)
prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides))
