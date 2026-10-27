# DouyinVN Studio 🎬

**DouyinVN Studio** là ứng dụng Windows Desktop chuyên nghiệp, hiện đại, được xây dựng bằng **Python 3.12** và **PySide6 (Qt for Python)**. Ứng dụng cung cấp giải pháp trọn gói cục bộ (100% Local AI, hoàn toàn miễn phí, không phụ thuộc API trả phí đám mây):
1. **Tiếp nhận video**: Hỗ trợ dán liên kết video Douyin (TikTok Trung Quốc) hoặc chọn file MP4 có sẵn trên máy tính (kèm tính năng kéo thả tiện lợi).
2. **Nhận dạng lời thoại tiếng Trung**: Sử dụng mô hình nhận dạng giọng nói **Faster-Whisper** (tiny, base, small, medium) với độ chính xác cao, trích xuất timestamp đồng bộ theo từng mili-giây.
3. **Dịch thuật sang tiếng Việt**: Sử dụng mô hình dịch nơ-ron **Helsinki-NLP/opus-mt-zh-vi** (Transformers & PyTorch CPU/GPU), chạy ngoại tuyến sau khi tải bộ nhớ đệm (cache), giữ nguyên ngữ cảnh và ngắt câu.
4. **Bảng chỉnh sửa phụ đề tương tác**: Cho phép người dùng duyệt và sửa đổi bản dịch tiếng Việt, chỉnh sửa mốc thời gian (timestamp), dịch chuyển timeline (+/-s), thêm/xóa dòng trước khi ghi lên video.
5. **Xóa phụ đề tiếng Trung đã đóng cứng**: Tích hợp với **Video-Subtitle-Remover (VSR)** bằng AI Inpainting (STTN, LaMa, ProPainter), đồng thời hỗ trợ bộ lọc làm mờ thông minh (FFmpeg boxblur / delogo) và chế độ bỏ qua (Skip).
6. **Ghi đè phụ đề tiếng Việt lên video**: Sử dụng **FFmpeg** ghi phụ đề trực tiếp (hardcode/burn-in), hỗ trợ đầy đủ font chữ tiếng Việt có dấu (Unicode), viền chữ chống chói, định dạng chuẩn video dọc 9:16 Douyin, và giữ nguyên 100% chất lượng âm thanh gốc.
7. **Quản lý hàng đợi và lịch sử**: Lưu trữ toàn bộ dữ liệu tác vụ và file trung gian vào cơ sở dữ liệu **SQLite** (chế độ WAL đa luồng), cho phép xem lại video kết quả, tiếp tục từ bước thất bại (resume).

---

## I. YÊU CẦU HỆ THỐNG

- **Hệ điều hành**: Windows 10 hoặc Windows 11 64-bit (ưu tiên Windows 11).
- **Python**: Phiên bản **3.12** (hỗ trợ cả `uv` và Python venv truyền thống).
- **FFmpeg & FFprobe**: Bắt buộc để đọc thông số và ghi phụ đề video.
  - Cài đặt nhanh qua Windows Terminal:
    ```powershell
    winget install Gyan.FFmpeg
    ```
- **Phần cứng**:
  - Tối thiểu: CPU 4 nhân, 8GB RAM, 10GB đĩa trống.
  - Khuyến nghị: NVIDIA GPU (GTX 1050 trở lên) để tăng tốc độ xử lý AI.

---

## II. CÀI ĐẶT NHANH (QUICK START)

### 1. Tự động thiết lập môi trường
Mở PowerShell tại thư mục dự án và chạy:
```powershell
.\install.ps1
```
Script sẽ tự động:
- Tạo môi trường ảo `.venv` với Python 3.12.
- Cài đặt các thư viện từ `requirements.txt`.
- Khởi tạo cấu trúc thư mục làm việc (`models`, `workspace`, `output`, `logs`, `data`).
- Kiểm tra toàn diện hệ thống.

### 2. Kiểm tra trạng thái môi trường
```powershell
.\check_environment.ps1
```

### 3. Khởi chạy ứng dụng
```powershell
.\run.ps1
```
Hoặc kích hoạt môi trường ảo:
```powershell
.venv\Scripts\python.exe app.py
```

---

## III. CẤU TRÚC THƯ MỤC DỰ ÁN

```
DouyinVNStudio/
├── app.py                      # Điểm khởi chạy chính của ứng dụng
├── requirements.txt            # Danh sách thư viện và phiên bản khóa
├── README.md                   # Tài liệu hướng dẫn sử dụng và kỹ thuật
├── install.ps1                 # Script cài đặt môi trường tự động
├── run.ps1                     # Script khởi chạy ứng dụng nhanh
├── check_environment.ps1       # Script kiểm tra điều kiện hệ thống
├── build_package.ps1           # Script đóng gói ứng dụng ra file EXE
├── DouyinVNStudio.spec         # Cấu hình đóng gói PyInstaller
├── pytest.ini                  # Cấu hình kiểm thử tự động
│
├── config/
│   ├── settings.py             # Quản lý cấu hình Pydantic
│   └── settings.json           # File lưu cấu hình đường dẫn và thông số
│
├── ui/
│   ├── main_window.py          # Cửa sổ chính giao diện Fluent dark theme
│   ├── video_preview.py        # Trình xem trước video và công cụ kéo chọn vùng chữ
│   ├── subtitle_editor.py      # Bảng chỉnh sửa phụ đề song ngữ và mốc thời gian
│   ├── task_queue.py           # Quản lý hàng đợi tác vụ và lịch sử
│   └── settings_dialog.py      # Hộp thoại cài đặt tham số hệ thống
│
├── core/
│   ├── downloader.py           # Bộ tải video Douyin và adapter yt-dlp
│   ├── media_probe.py          # Kiểm tra thông số video (FFprobe)
│   ├── speech_to_text.py       # Nhận dạng tiếng Trung (Faster-Whisper)
│   ├── translator.py           # Dịch thuật Trung - Việt (Helsinki-NLP)
│   ├── subtitle_remover.py     # Module xóa phụ đề (VSR / FFmpeg)
│   ├── subtitle_renderer.py    # Ghi phụ đề tiếng Việt lên video (FFmpeg)
│   ├── ocr_subtitles.py        # Module OCR bổ trợ chữ trên hình
│   └── pipeline.py             # Điều phối 8 giai đoạn xử lý khép kín
│
├── workers/
│   └── processing_worker.py    # Luồng nền QThread không gây đơ giao diện
│
├── storage/
│   ├── database.py             # Kết nối SQLite & WAL mode
│   └── task_repository.py      # CRUD tác vụ và quản lý phụ đề
│
├── tests/                      # Bộ kiểm thử tự động (Unit & Integration tests)
├── workspace/                  # Thư mục chứa các file tạm từng tác vụ
├── models/                     # Thư mục lưu trữ bộ nhớ đệm mô hình AI (Offline)
├── output/                     # Thư mục xuất video MP4 và file SRT thành phẩm
├── logs/                       # Nhật ký ghi nhận hoạt động và lỗi
└── data/                       # Cơ sở dữ liệu SQLite (douyinvn.db)
```

---

## IV. QUY TRÌNH XỬ LÝ (PIPELINE)

Pipeline gồm 8 bước tuần tự, có khả năng phục hồi và tiếp tục từ bước thất bại:

1. **Acquire (Tiếp nhận)**:
   - Nhập liên kết chia sẻ Douyin (tự bóc tách link gốc và tải stream không logo) hoặc nạp file MP4 có sẵn.
2. **Inspect (Phân tích)**:
   - Đọc độ phân giải, tỷ lệ khung hình (dọc 9:16), FPS, thời lượng, codec, track âm thanh và kiểm tra dung lượng đĩa trống.
3. **Transcribe (Nhận dạng tiếng Trung)**:
   - Faster-Whisper chuyển đổi lời thoại thành các câu kèm timestamp và xuất `transcript_zh.json` & `transcript_zh.srt`.
4. **Translate (Dịch tiếng Việt)**:
   - Mô hình `opus-mt-zh-vi` dịch song ngữ, bảo toàn timestamp, xuất `transcript_vi.json` & `subtitles_vi.srt`.
5. **Review (Kiểm tra & Chỉnh sửa)**:
   - Giao diện tự động dừng ở bước này (nếu tắt chế độ Auto) để người dùng xem lại, sửa từ ngữ, điều chỉnh lệch giây (+/-s) hoặc thêm bớt câu.
6. **Remove Subtitles (Xóa phụ đề Trung)**:
   - Chạy VSR AI Inpainting hoặc làm mờ vùng chữ bằng FFmpeg (boxblur/delogo). Có thể bỏ qua (Skip) nếu video gốc không có chữ che khuất.
7. **Render (Ghi phụ đề Việt)**:
   - FFmpeg biên dịch phụ đề trực tiếp lên hình với font có dấu (Segoe UI / Arial), viền chữ tương phản cao, giữ nguyên 100% âm thanh gốc.
8. **Validate (Xác thực)**:
   - Chạy FFprobe kiểm tra luồng video đầu ra, dung lượng và thời lượng thực tế trước khi báo hoàn tất.

---

## V. TÍCH HỢP VSR (VIDEO-SUBTITLE-REMOVER)

Nếu bạn muốn sử dụng tính năng xóa chữ nâng cao bằng AI Inpainting của VSR:
1. Tải bản phát hành hoặc clone repository chính thức:
   - Repository: https://github.com/YaoFANGUK/video-subtitle-remover
   - Releases: https://github.com/YaoFANGUK/video-subtitle-remover/releases
2. Mở DouyinVN Studio, chọn **⚙️ Cài đặt** -> mục **VSR (Video-Subtitle-Remover)**.
3. Chọn đường dẫn tới thư mục chứa `backend/main.py` hoặc file `video-subtitle-remover.exe`.
4. Chọn thuật toán Inpainting (`sttn-auto`, `lama`, `propainter`...).
5. *Lưu ý*: Nếu chưa cài đặt VSR, ứng dụng tự động cung cấp giải pháp làm mờ chữ bằng FFmpeg hoặc bỏ qua bước này để video xuất bình thường.

---

## VI. BỘ KIỂM THỬ (TEST SUITE)

Để chạy kiểm thử tự động toàn diện:
```powershell
.venv\Scripts\pytest.exe -v
```
Toàn bộ **30 bài kiểm thử** bao gồm:
- Phân tích video, đọc stream, kiểm tra dung lượng đĩa và trích xuất thumbnail.
- Định dạng mốc thời gian SRT và nhận dạng giọng nói.
- Dịch thuật ngoại tuyến với tiếng Việt có dấu.
- Các chế độ xóa phụ đề (Skip, FFmpeg Delogo, FFmpeg Blur).
- Trình ghi phụ đề FFmpeg, cơ chế escape ký tự đặc biệt đường dẫn Windows.
- Phân tích liên kết Douyin và bóc tách URL chia sẻ.
- Cơ sở dữ liệu SQLite và lưu trữ tác vụ.
- Tích hợp pipeline, dừng để duyệt phụ đề, tiếp tục chạy (resume), và hủy tác vụ an toàn.

---

## VII. ĐÓNG GÓI THÀNH FILE EXE ĐỘC LẬP

Để đóng gói ứng dụng cho Windows:
```powershell
.\build_package.ps1
```
Ứng dụng hoàn chỉnh sẽ được tạo tại thư mục:
`dist\DouyinVNStudio\DouyinVNStudio.exe`

---

## VIII. GIẤY PHÉP & BẢN QUYỀN

- Mã nguồn DouyinVN Studio phát hành theo giấy phép **MIT**.
- Các mô hình AI sử dụng:
  - Faster-Whisper: Giấy phép MIT / Apache 2.0.
  - Helsinki-NLP/opus-mt-zh-vi: Giấy phép CC-BY-4.0.
  - FFmpeg: Giấy phép LGPL / GPL.
