# -*- coding: utf-8 -*-
"""
Script generating comprehensive Word (.docx) documentation for DouyinVN Studio.
Covers system architecture, AI models, subtitle removal techniques, and step-by-step user guide.
"""

import os
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, color_hex):
    """Set background color of a table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    tc_pr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set padding inside a table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tc_pr.append(tc_mar)

def add_callout_box(doc, text, title="LƯU Ý QUAN TRỌNG", bg_color="F1F5F9", border_color="0284C7"):
    """Add a stylish callout box with a colored left border."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    set_cell_background(cell, bg_color)
    set_cell_margins(cell, top=140, bottom=140, left=200, right=200)
    
    # Border: thick left, none for others
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="none"/>'
        f'<w:left w:val="single" w:sz="36" w:space="0" w:color="{border_color}"/>'
        f'<w:bottom w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tc_pr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    
    run_title = p.add_run(f"📌 {title}: ")
    run_title.bold = True
    run_title.font.name = "Segoe UI"
    run_title.font.size = Pt(10.5)
    run_title.font.color.rgb = RGBColor(2, 132, 199)
    
    run_text = p.add_run(text)
    run_text.font.name = "Segoe UI"
    run_text.font.size = Pt(10.5)
    run_text.font.color.rgb = RGBColor(30, 41, 59)
    
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

def format_table_headers(table, headers, bg_color="0A2540"):
    """Style header row of a table."""
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], bg_color)
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=150, right=150)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in p.runs:
            run.font.name = "Segoe UI"
            run.font.size = Pt(10)
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)

def build_docx(output_path: str):
    doc = docx.Document()
    
    # 1. Page Margins
    for sec in doc.sections:
        sec.top_margin = Inches(0.8)
        sec.bottom_margin = Inches(0.8)
        sec.left_margin = Inches(0.9)
        sec.right_margin = Inches(0.9)
    
    # Base Normal Style
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Segoe UI'
    style_normal.font.size = Pt(11)
    style_normal.font.color.rgb = RGBColor(51, 65, 85) # Slate 700
    style_normal.paragraph_format.line_spacing = 1.2
    style_normal.paragraph_format.space_after = Pt(6)

    # -------------------------------------------------------------
    # COVER / HEADER TITLE
    # -------------------------------------------------------------
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(20)
    title_p.paragraph_format.space_after = Pt(4)
    run_app = title_p.add_run("🎬 DOUYINVN STUDIO v1.0.0")
    run_app.font.name = "Segoe UI"
    run_app.font.size = Pt(24)
    run_app.font.bold = True
    run_app.font.color.rgb = RGBColor(10, 37, 64) # Deep Navy

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(18)
    run_sub = sub_p.add_run("HỆ THỐNG AI XỬ LÝ VIDEO, TỰ ĐỘNG XÓA PHỤ ĐỀ TIẾNG TRUNG\nVÀ TẠO PHỤ ĐỀ TIẾNG VIỆT CHUYÊN NGHIỆP (100% OFFLINE)")
    run_sub.font.name = "Segoe UI"
    run_sub.font.size = Pt(13)
    run_sub.font.bold = True
    run_sub.font.color.rgb = RGBColor(2, 132, 199) # Sky Blue

    # Info banner table
    meta_table = doc.add_table(rows=4, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_info = [
        ("Tài liệu:", "Báo cáo Kiến trúc Công nghệ & Cẩm nang Hướng dẫn Sử dụng"),
        ("Môi trường:", "Windows 10 / 11 (64-bit) - Độc lập, Không cần cài đặt Python"),
        ("Chế độ vận hành:", "100% Ngoại tuyến (Offline Local AI) - Bảo mật dữ liệu tuyệt đối"),
        ("Ngày phát hành:", "Tháng 10/2026 - Bản cập nhật v1.0.0 chính thức")
    ]
    for row_idx, (k, v) in enumerate(meta_info):
        c0, c1 = meta_table.cell(row_idx, 0), meta_table.cell(row_idx, 1)
        c0.width = Inches(2.2)
        c1.width = Inches(4.5)
        set_cell_background(c0, "F8FAFC")
        set_cell_background(c1, "F8FAFC")
        set_cell_margins(c0, top=60, bottom=60, left=100, right=100)
        set_cell_margins(c1, top=60, bottom=60, left=100, right=100)
        p0 = c0.paragraphs[0]
        r0 = p0.add_run(k)
        r0.bold = True
        r0.font.size = Pt(9.5)
        r0.font.color.rgb = RGBColor(71, 85, 105)
        p1 = c1.paragraphs[0]
        r1 = p1.add_run(v)
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # -------------------------------------------------------------
    # MỤC LỤC TỔNG QUAN
    # -------------------------------------------------------------
    def add_heading_1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(text)
        r.font.name = "Segoe UI"
        r.font.size = Pt(15)
        r.font.bold = True
        r.font.color.rgb = RGBColor(10, 37, 64)
        return p

    def add_heading_2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(text)
        r.font.name = "Segoe UI"
        r.font.size = Pt(12.5)
        r.font.bold = True
        r.font.color.rgb = RGBColor(2, 132, 199)
        return p

    def add_heading_3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(text)
        r.font.name = "Segoe UI"
        r.font.size = Pt(11)
        r.font.bold = True
        r.font.color.rgb = RGBColor(51, 65, 85)
        return p

    # -------------------------------------------------------------
    # PHẦN 1: GIỚI THIỆU TỔNG QUAN
    # -------------------------------------------------------------
    add_heading_1("I. TỔNG QUAN VỀ PHẦN MỀM DOUYINVN STUDIO")
    
    p = doc.add_paragraph()
    p.add_run(
        "DouyinVN Studio là giải pháp phần mềm máy trạm (Desktop Application) cao cấp, được phát triển chuyên biệt "
        "nhằm tự động hóa toàn diện quy trình chuyển đổi, biên dịch và bản địa hóa các video ngắn tiếng Trung "
        "(từ nền tảng Douyin, TikTok Trung Quốc, Kuaishou, Bilibili) sang video có phụ đề tiếng Việt chuẩn xác, thẩm mỹ cao.\n"
        "Trước đây, việc 'reup' hoặc làm nội dung video từ Trung Quốc đòi hỏi nhiều thao tác thủ công phức tạp: "
        "tải video, dùng phần mềm cắt/làm mờ phụ đề cũ, nghe chép lời thoại bằng tay, dịch từng câu và căn chỉnh lại timeline. "
        "DouyinVN Studio tích hợp toàn bộ chuỗi mắt xích này vào một quy trình tự động hóa khép kín (Pipeline) chỉ với 1 cú click chuột."
    )

    add_callout_box(
        doc,
        "DouyinVN Studio được đóng gói độc lập theo chuẩn Onedir/PyInstaller. Toàn bộ các mô hình trí tuệ nhân tạo (AI), "
        "động cơ suy luận (Inference Engine) và bộ công cụ xử lý đa phương tiện FFmpeg đều nằm trọn vẹn trong thư mục máy tính. "
        "Phần mềm cam kết chạy 100% Offline, không gửi dữ liệu ra máy chủ bên ngoài, không yêu cầu API Key trả phí và "
        "đảm bảo an toàn bảo mật tuyệt đối cho mọi dữ liệu của người dùng.",
        title="ĐẶC TRƯNG CỐT LÕI - 100% OFFLINE & RIÊNG TƯ"
    )

    # -------------------------------------------------------------
    # PHẦN 2: KIẾN TRÚC CÔNG NGHỆ & CÁC MÔ HÌNH AI
    # -------------------------------------------------------------
    add_heading_1("II. KIẾN TRÚC CÔNG NGHỆ VÀ CÁC MÔ HÌNH AI BÊN TRONG")

    p = doc.add_paragraph()
    p.add_run(
        "Phần mềm được xây dựng trên mô hình đường ống phân tầng (Pipelined Architecture), "
        "trong đó mỗi giai đoạn được đảm nhiệm bởi một mô hình trí tuệ nhân tạo hoặc thuật toán chuyên biệt:"
    )

    # Table of AI Components
    tbl_tech = doc.add_table(rows=5, cols=4)
    tbl_tech.alignment = WD_TABLE_ALIGNMENT.CENTER
    format_table_headers(tbl_tech, ["Phân hệ / Tác vụ", "Mô hình / Động cơ AI", "Cơ chế kỹ thuật", "Đặc tính nổi bật"])
    
    tech_data = [
        ("1. Nhận dạng giọng nói (Speech-to-Text)", "Faster-Whisper (CTranslate2)", "Encoder-Decoder Transformer, lượng tử hóa INT8 / FP16", "Nhận dạng tiếng Trung cực nhạy, phân đoạn timestamp theo câu."),
        ("2. Nhận diện chữ video (Video OCR)", "RapidOCR v4 (PaddleOCR ONNX)", "DBNet (Detection) + LCNet-SVTR (Recognition)", "Tự động quét chữ chạy, tiêu đề, chữ ở trung tâm khi video không có tiếng."),
        ("3. Dịch thuật Trung - Việt (Translation)", "MarianMT / Opus-MT (Helsinki)", "Sequence-to-Sequence NMT chuyên ngữ cảnh Trung-Việt", "Dịch thoát ý, tự động lọc hashtag và chuyển đổi từ ngữ văn hóa mạng."),
        ("4. Xóa chữ & Phục hồi nét (Inpaint / Restore)", "FFmpeg Delogo + Unsharp Mask", "Nội suy biên cục bộ đa điểm + Tái tạo tương phản vi mô", "Xóa sạch chữ mọi vị trí theo thời gian thực (Time-gated) và tăng độ sắc nét.")
    ]
    
    for r_idx, row_values in enumerate(tech_data, start=1):
        for c_idx, val in enumerate(row_values):
            cell = tbl_tech.cell(r_idx, c_idx)
            set_cell_background(cell, "FFFFFF" if r_idx % 2 != 0 else "F8FAFC")
            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            cp = cell.paragraphs[0]
            cr = cp.add_run(val)
            cr.font.size = Pt(9.5)
            if c_idx == 0:
                cr.bold = True
                cr.font.color.rgb = RGBColor(10, 37, 64)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    add_heading_2("1. Công nghệ Nhận dạng Lời thoại (Faster-Whisper)")
    p = doc.add_paragraph()
    p.add_run(
        "Đối với các video có thuyết minh hoặc hội thoại nhân vật, DouyinVN Studio sử dụng Faster-Whisper – "
        "bản tối ưu hóa hàng đầu của OpenAI Whisper dựa trên CTranslate2. Động cơ này nhanh gấp 4 lần so với bản gốc "
        "nhờ tận dụng tối đa tập lệnh AVX2/AVX-512 trên CPU hoặc Tensor Cores trên GPU NVIDIA.\n"
        "• Khả năng tự động lọc bỏ tạp âm, tiếng ồn nền của video.\n"
        "• Độ chính xác vượt trội với các phương ngữ tiếng Trung phổ thông (Mandarin).\n"
        "• Định vị chính xác thời điểm bắt đầu (Start) và kết thúc (End) của từng câu thoại."
    )

    add_heading_2("2. Công nghệ Nhận diện Chữ chạy trên Màn hình (RapidOCR v4)")
    p = doc.add_paragraph()
    p.add_run(
        "Rất nhiều video Douyin (đặc biệt là video review đồ chơi, unboxing, biến hình mô hình, ASMR) "
        "hoàn toàn không có lời thoại mà chỉ chèn chữ thuyết minh trực tiếp lên khung hình. "
        "Nếu chỉ dựa vào âm thanh, các phần mềm thông thường sẽ thất bại hoàn toàn.\n"
        "DouyinVN Studio giải quyết triệt để vấn đề này nhờ tích hợp động cơ RapidOCR v4 chạy trên nền tảng ONNX Runtime:\n"
        "• Khối Phát hiện viền chữ (DBNet): Quét và cô lập vùng chữ nhật bao quanh mọi dòng chữ tiếng Trung.\n"
        "• Khối Phân loại góc nghiêng (Angle Classifier): Tự động xoay chữ về hướng ngang chuẩn xác.\n"
        "• Khối Nhận dạng ký tự (SVTR-LCNet): Giải mã chính xác hàng ngàn ký tự Hán tự phức tạp.\n"
        "• Thuật toán Gom cụm Không - Thời gian (Spatiotemporal Clustering): Tự động theo dõi các dòng chữ "
        "xuất hiện qua nhiều khung hình liên tiếp và kết hợp thành các phụ đề có thời lượng hiển thị mượt mà."
    )

    add_heading_2("3. Thuật toán Xóa Chữ Đa điểm & Tái tạo Độ nét (Time-Gated Delogo & Unsharp)")
    p = doc.add_paragraph()
    p.add_run(
        "Đây là cải tiến công nghệ đột phá của phiên bản v1.0.0:\n"
        "• Khắc phục nhược điểm 'xóa cố định một vùng': Trước đây, việc xóa chữ chỉ được đặt ở đỉnh hoặc đáy video, "
        "dẫn tới việc bỏ sót chữ xuất hiện ở giữa trung tâm màn hình (ví dụ: dòng chữ '搅拌车与铲车变组合模式' "
        "ngay dưới xe đồ chơi trong video). Bản v1.0.0 tự động nhận diện và tính toán tọa độ (X, Y, Width, Height) "
        "của mọi vị trí chữ trên toàn bộ khung hình.\n"
        "• Kích hoạt xóa theo thời gian thực (Time-gated Delogo): Bộ lọc chỉ áp dụng đúng trong các giây xuất hiện chữ "
        "(enable='between(t, start, end)'). Ngay khi chữ kết thúc, khu vực giữa màn hình lập tức trả về nguyên vẹn "
        "100% hình ảnh gốc, không để lại bất kỳ vệt mờ hay vết cắt đen nào đè lên chủ thể.\n"
        "• Bộ lọc Khôi phục Độ sắc nét (Unsharp Mask Detail Restoration): Áp dụng thuật toán unsharp=lx=5:ly=5:la=0.7 "
        "giúp tái tạo viền cạnh và độ tương phản vi mô của vật thể, giúp video thành phẩm rõ nét, loại bỏ hoàn toàn cảm giác mờ đục."
    )

    add_heading_2("4. Động cơ Dịch thuật Nơ-ron (Neural Machine Translation)")
    p = doc.add_paragraph()
    p.add_run(
        "Sử dụng mô hình ngôn ngữ MarianMT chuyên biệt cặp Trung - Việt (Helsinki-NLP/opus-mt-zh-vi). "
        "Hệ thống được lập trình kèm bộ lọc xử lý ngữ cảnh:\n"
        "• Tự động loại bỏ các hashtag rác (#大力神 #变形玩具 #MAGIC模玩) không làm loãng nội dung phụ đề.\n"
        "• Tối ưu ngữ pháp tiếng Việt, câu văn tự nhiên, gãy gọn, đúng văn phong đời sống."
    )

    # -------------------------------------------------------------
    # PHẦN 3: HƯỚNG DẪN SỬ DỤNG
    # -------------------------------------------------------------
    add_heading_1("III. HƯỚNG DẪN SỬ DỤNG CHI TIẾT TỪ A ĐẾN Z")

    p = doc.add_paragraph()
    p.add_run(
        "Giao diện của DouyinVN Studio được tối ưu hóa cho người dùng văn phòng và sáng tạo nội dung, "
        "gồm 3 khu vực chính: 🚀 Xử lý Video (Dashboard) - ✍️ Chỉnh sửa phụ đề - 📋 Hàng đợi tác vụ."
    )

    add_heading_2("Bước 1: Khởi động ứng dụng")
    p = doc.add_paragraph()
    p.add_run(
        "Vào thư mục dist\\DouyinVNStudio, nhấp đúp vào file DouyinVNStudio.exe. "
        "Quan sát thanh trạng thái ở góc trên cùng bên phải, ứng dụng sẽ báo:\n"
        "  [ FFmpeg: Sẵn sàng | Xóa chữ: Delogo + Tái tạo nét (Tự động) ]"
    )

    add_heading_2("Bước 2: Nạp video đầu vào")
    p = doc.add_paragraph()
    p.add_run(
        "Bác có thể đưa video vào phần mềm theo một trong hai cách cực kỳ thuận tiện:\n"
        "• Cách 1 - Dán link Douyin / TikTok: Sao chép liên kết video từ ứng dụng Douyin (hoặc trình duyệt), "
        "dán vào ô nhập liệu và bấm '⚡ Phân tích URL'. Phần mềm sẽ tự động tải video gốc chất lượng cao không logo.\n"
        "• Cách 2 - Chọn file từ máy tính: Bấm nút '📁 Chọn video từ máy...' và chọn file video MP4/MKV có sẵn "
        "(hoặc đơn giản là kéo thả trực tiếp file video từ cửa sổ Windows vào giao diện phần mềm)."
    )

    add_heading_2("Bước 3: Chọn chế độ và Bắt đầu xử lý")
    p = doc.add_paragraph()
    p.add_run(
        "1. Kiểm tra tùy chọn 'Tự động xử lý toàn bộ (Khuyên dùng)': Khi được chọn, phần mềm sẽ tự chạy qua tất cả "
        "8 giai đoạn (Tiếp nhận -> Phân tích -> Nhận dạng tiếng/chữ -> Dịch tiếng Việt -> Xóa phụ đề Trung -> Ghi đè phụ đề Việt -> Kiểm tra).\n"
        "2. Kiểm tra tùy chọn 'Phương pháp xóa chữ': Mặc định là 'Xóa vùng chữ bằng FFmpeg (Delogo)' (chế độ tốt nhất).\n"
        "3. Bấm nút lớn màu xanh: '🚀 BẮT ĐẦU XỬ LÝ VIDEO'.\n"
        "Theo dõi thanh tiến độ phần trăm và nhật ký thời gian thực trong khung 'Nhật ký xử lý chi tiết'."
    )

    add_heading_2("Bước 4: Kiểm tra và chỉnh sửa phụ đề (Tùy chọn)")
    p = doc.add_paragraph()
    p.add_run(
        "Nếu bác tắt tùy chọn 'Tự động xử lý toàn bộ', phần mềm sẽ tự dừng lại ở tiến độ 75% và chuyển bác sang "
        "Tab '✍️ Chỉnh sửa phụ đề'. Tại đây:\n"
        "• Bác có thể sửa lại câu từ tiếng Việt theo ý muốn.\n"
        "• Chỉnh sửa thời gian hiển thị (Start / End) của từng câu.\n"
        "• Bấm '💾 Lưu bản dịch' và bấm '🎬 TIẾP TỤC XUẤT VIDEO' để hoàn tất."
    )

    add_heading_2("Bước 5: Thưởng thức video thành phẩm")
    p = doc.add_paragraph()
    p.add_run(
        "Khi tiến độ đạt 100%, một hộp thoại chúc mừng sẽ xuất hiện:\n"
        "• Bác chỉ cần bấm 'Mở video thành phẩm' để xem trực tiếp video đã được làm sạch chữ Trung Quốc "
        "và gắn phụ đề tiếng Việt sắc nét.\n"
        "• File video và file phụ đề .SRT độc lập luôn được lưu sẵn trong thư mục output của phần mềm."
    )

    # -------------------------------------------------------------
    # PHẦN 4: HƯỚNG DẪN CẤU HÌNH NÂNG CAO
    # -------------------------------------------------------------
    add_heading_1("IV. CẤU HÌNH NÂNG CAO (NÚT ⚙️ CÀI ĐẶT)")

    p = doc.add_paragraph()
    p.add_run(
        "Bấm vào nút '⚙️ Cài đặt' ở góc trên cùng bên phải để mở cửa sổ tinh chỉnh các thông số chuyên sâu:"
    )

    tbl_settings = doc.add_table(rows=6, cols=3)
    tbl_settings.alignment = WD_TABLE_ALIGNMENT.CENTER
    format_table_headers(tbl_settings, ["Mục cài đặt", "Tùy chọn khả dụng", "Khuyến nghị sử dụng"])
    
    settings_data = [
        ("Kích thước Model Whisper", "tiny, base, small, medium", "Chọn 'tiny' nếu cần tốc độ cực nhanh; chọn 'base' hoặc 'small' nếu video có nhạc ồn hoặc phát âm khó."),
        ("Thiết bị xử lý (Device)", "cpu, cuda, auto", "Nếu máy tính có card đồ họa rời NVIDIA (GTX/RTX), chọn 'cuda' để tăng tốc xử lý lên gấp 5-10 lần."),
        ("Kiểu tính toán (Compute)", "int8, float16, float32", "Dùng 'int8' khi chạy trên CPU để tiết kiệm RAM. Dùng 'float16' khi chạy trên GPU CUDA."),
        ("Phương pháp xóa chữ", "ffmpeg_delogo, ffmpeg_blur, vsr, skip", "Luôn để 'ffmpeg_delogo' để được hưởng lợi từ thuật toán xóa đa điểm và làm nét unsharp."),
        ("Định dạng phụ đề Việt", "Font, Cỡ chữ, Màu sắc, Viền, Lề dưới", "Font mặc định 'Segoe UI' hoặc 'Arial', Cỡ 24, Màu trắng viền đen dày 2.5px chống chìm hình.")
    ]

    for r_idx, row_values in enumerate(settings_data, start=1):
        for c_idx, val in enumerate(row_values):
            cell = tbl_settings.cell(r_idx, c_idx)
            set_cell_background(cell, "FFFFFF" if r_idx % 2 != 0 else "F8FAFC")
            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            cp = cell.paragraphs[0]
            cr = cp.add_run(val)
            cr.font.size = Pt(9.5)
            if c_idx == 0:
                cr.bold = True
                cr.font.color.rgb = RGBColor(10, 37, 64)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # -------------------------------------------------------------
    # PHẦN 5: CÂU HỎI THƯỜNG GẶP (FAQ)
    # -------------------------------------------------------------
    add_heading_1("V. CÂU HỎI THƯỜNG GẶP & MẸO XỬ LÝ SỰ CỐ")

    add_heading_2("1. Video hoàn toàn không có lời thoại thì phần mềm có tạo được phụ đề không?")
    p = doc.add_paragraph()
    p.add_run(
        "Có! Đây chính là thế mạnh đặc biệt của DouyinVN Studio. Khi phát hiện video không có âm thanh giọng nói, "
        "hệ thống tự động chuyển sang chế độ quét thị giác OCR (RapidOCR v4). Mọi tiêu đề, phụ đề chữ Hán gắn trên video "
        "sẽ được nhận diện, dịch sang tiếng Việt và khớp thời gian chính xác như một bản dịch lời thoại thông thường."
    )

    add_heading_2("2. Tại sao chữ ở giữa màn hình hoặc các góc khác nhau vẫn được xóa sạch?")
    p = doc.add_paragraph()
    p.add_run(
        "Nhờ thuật toán Dynamic Timeline Clustering, phần mềm quét toàn bộ ma trận điểm ảnh của video. "
        "Bất kể chữ xuất hiện ở đỉnh (Top Banner), ở đáy (Bottom Subtitle) hay ở trung tâm (Center Title), "
        "hệ thống đều tính toán tọa độ hộp bao riêng biệt cho từng đoạn và áp dụng bộ lọc delogo theo đúng khoảng thời gian xuất hiện."
    )

    add_heading_2("3. Tôi có cần kết nối Internet khi sử dụng phần mềm không?")
    p = doc.add_paragraph()
    p.add_run(
        "Không cần! Toàn bộ mô hình AI và các thư viện xử lý đã được nạp sẵn trong máy. Bác có thể ngắt kết nối mạng hoàn toàn "
        "khi xử lý các file video có sẵn trên máy tính. Internet chỉ cần thiết khi bác dán đường link Douyin/TikTok để tải video từ web về."
    )

    add_heading_2("4. Tên file video có ký tự đặc biệt hoặc dấu hashtag (#) có bị lỗi không?")
    p = doc.add_paragraph()
    p.add_run(
        "Hệ thống đã tích hợp sẵn module sanitize_output_name. Mọi ký tự nhạy cảm với hệ điều hành Windows như "
        "dấu thăng (#), dấu hỏi (?), dấu hai chấm (:), dấu ngoặc kép... đều được tự động làm sạch và chuẩn hóa, "
        "đảm bảo các trình phát video hệ thống (Windows Media Player, VLC, Movies & TV) luôn mở thành công mà không bao giờ gặp lỗi 'Server execution failed'."
    )

    # -------------------------------------------------------------
    # KẾT LUẬN & LIÊN HỆ
    # -------------------------------------------------------------
    add_heading_1("VI. LỜI KẾT")
    p = doc.add_paragraph()
    p.add_run(
        "DouyinVN Studio v1.0.0 là công cụ hoàn hảo, mạnh mẽ và ổn định dành cho bất kỳ ai muốn tự động hóa quy trình "
        "biên dịch nội dung video tiếng Trung sang tiếng Việt một cách chuyên nghiệp, nhanh chóng và bảo mật cao nhất.\n"
        "Chúc bác có những trải nghiệm tuyệt vời và tạo ra thật nhiều video triệu view với DouyinVN Studio!"
    )

    # Save document
    doc.save(output_path)
    print(f"Documentation successfully created at: {output_path}")

if __name__ == "__main__":
    out_file = r"C:\Users\VI_DOAN\Desktop\DouYin\Tai_Lieu_Huong_Dan_Va_Cong_Nghe_DouyinVN_Studio.docx"
    build_docx(out_file)
