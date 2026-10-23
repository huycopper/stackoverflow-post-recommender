# 04. Data contract

> **Version: 0.1 (DRAFT)**. Bản nháp do ETL đề xuất, **chưa được bên model (Hung) duyệt**. Sẽ chốt thành 1.0 sau khi có dữ liệu mẫu thật.

Đây là **giao diện giữa ETL và bên model**. ETL cam kết xuất đúng định dạng này. Bên model chỉ đọc từ các bảng ở mục 2 và 3, không đọc dữ liệu thô.

Quy tắc thay đổi:

- Thêm trường mới không bắt buộc: tăng minor version (0.1 → 0.2).
- Đổi tên, đổi kiểu hoặc xóa trường: tăng major version, và cần cả ETL lẫn bên model duyệt PR.
- Mọi thay đổi đều ghi vào mục Changelog cuối file và thêm một mục vào [decisions.md](decisions.md).

## 1. Dữ liệu thô: `data/raw/`

- Response nguyên văn từ API, mỗi dòng một response: `data/raw/{endpoint}/{YYYYMMDD}.jsonl.gz`.
- Mỗi dòng có dạng `{"fetched_at": "...", "url": "...", "params": {...}, "response": {...}}`.
- **Không sửa, chỉ ghi thêm.** Không commit lên git.

## 2. Dữ liệu sạch: `data/clean/` (Parquet)

Thời gian lưu dạng `timestamp[us, UTC]`. ID là ID gốc trên Stack Overflow.

### `questions.parquet`

| Trường | Kiểu | Null? | Mô tả |
|---|---|---|---|
| `question_id` | int64 | không | Khóa chính |
| `title` | string | không | Đã giải mã ký tự HTML |
| `body_text` | string | không | Body đã bóc HTML, **không chứa code khối** |
| `body_code` | list\<string\> | không | Các khối code (`<pre>`), có thể rỗng |
| `tags` | list\<string\> | không | Viết thường, đã chuẩn hóa |
| `score` | int32 | có | |
| `view_count` | int32 | có | |
| `answer_count` | int32 | không | Số câu trả lời đã lấy được |
| `comment_count` | int32 | không | Số comment **sau khi lọc** |
| `creation_date` | timestamp | không | |
| `is_closed_duplicate` | bool | không | Bị đóng vì trùng |
| `link` | string | không | URL câu hỏi, dùng để trích nguồn |

### `answers.parquet`

| Trường | Kiểu | Null? | Mô tả |
|---|---|---|---|
| `answer_id` | int64 | không | Khóa chính |
| `question_id` | int64 | không | Khóa ngoại tới `questions` |
| `body_text` | string | không | |
| `body_code` | list\<string\> | không | |
| `score` | int32 | có | |
| `is_accepted` | bool | không | |
| `creation_date` | timestamp | không | |

### `comments.parquet`

| Trường | Kiểu | Null? | Mô tả |
|---|---|---|---|
| `comment_id` | int64 | không | Khóa chính |
| `post_id` | int64 | không | ID câu hỏi hoặc câu trả lời |
| `post_type` | string | không | `question` hoặc `answer` |
| `question_id` | int64 | không | Câu hỏi gốc của thread, để join nhanh |
| `text` | string | không | Đã bóc HTML và chuẩn hóa |
| `score` | int32 | có | |
| `creation_date` | timestamp | không | |

Các comment làm lộ đáp án (ví dụ "Possible duplicate of…") **đã bị loại** ở bước làm sạch ([05](05_cleaning_pipeline.md), bước 2).

### `duplicate_pairs.parquet`

| Trường | Kiểu | Null? | Mô tả |
|---|---|---|---|
| `duplicate_id` | int64 | không | Câu hỏi bị đóng vì trùng |
| `original_id` | int64 | không | Câu hỏi gốc |

Cặp này có hướng. Đã bỏ các cặp tự trỏ về chính nó và các cặp mà một trong hai câu không có trong `questions`.

### `duplicate_groups.parquet`

| Trường | Kiểu | Null? | Mô tả |
|---|---|---|---|
| `question_id` | int64 | không | |
| `group_id` | int64 | không | Thành phần liên thông của đồ thị trùng |

### `splits.parquet`

| Trường | Kiểu | Null? | Mô tả |
|---|---|---|---|
| `question_id` | int64 | không | |
| `split` | string | không | `train`, `val` hoặc `test`. **Chia theo `group_id`** |

## 3. Dữ liệu đưa vào model: `data/clean/documents.parquet`

Mỗi dòng là một câu hỏi, đã ghép sẵn văn bản cho từng cấu hình thí nghiệm.

| Trường | Kiểu | Mô tả |
|---|---|---|
| `question_id` | int64 | |
| `text_content` | string | `title` + `body_text`. Dùng cho cấu hình `C` |
| `text_comments` | string | Các comment của câu hỏi, nối theo thời gian. Dùng cho cấu hình `C+Cm` |
| `text_answers` | string | Câu trả lời được chấp nhận hoặc điểm cao nhất. Dùng cho cấu hình `C+Cm+A` (tùy chọn) |
| `tags` | list\<string\> | |
| `split` | string | |

## Câu hỏi mở cần chốt với bên model

- [ ] `text_comments` lấy cả comment của câu trả lời, hay chỉ comment của câu hỏi?
- [ ] Có giữ code (`body_code`) trong văn bản đưa vào model không, hay bỏ hẳn?
- [ ] Có cắt độ dài văn bản không (model dạng transformer giới hạn số token)?
- [ ] Định dạng lưu là Parquet, hay JSONL để dễ đọc?

## Changelog

- **0.1** (23/10/2026): bản nháp đầu tiên.
