# 04. Data contract

> **Version: 0.4 (DRAFT)**. Hung đã gửi định dạng đầu vào model mong muốn (23/10/2026, mục 3). ETL cần xác nhận với Hung các trường bổ sung ở mục 3, sau đó chốt thành 1.0.

Đây là **giao diện giữa phần làm sạch và những ai dùng dữ liệu sạch**. ETL cam kết xuất đúng định dạng này. Người dùng chỉ đọc từ các bảng ở mục 2 và 3, không đọc dữ liệu thô.

Quy tắc thay đổi:

- Thêm trường mới không bắt buộc: tăng minor version (0.1 → 0.2).
- Đổi tên, đổi kiểu hoặc xóa trường: tăng major version, và cần cả ETL lẫn bên model duyệt PR.
- Mọi thay đổi đều ghi vào mục Changelog cuối file và thêm một mục vào [decisions.md](decisions.md).
- Trước bản 1.0 đây vẫn là bản nháp: được đổi tên hoặc đổi trường mà chỉ cần tăng minor version, miễn là ghi changelog.

## 1. Dữ liệu thô: `data/raw/`

- Response nguyên văn từ API, mỗi dòng một response: `data/raw/{endpoint}/{YYYYMMDD}.jsonl.gz` (ngày theo UTC).
- `endpoint` ∈ `filters`, `questions`, `questions_linked`, `questions_by_id`, `answers`, `question_comments`, `answer_comments`. Ý nghĩa từng loại xem [03](03_data_source.md#các-endpoint-đang-dùng).
- Mỗi dòng có dạng `{"fetched_at": "<ISO UTC>", "endpoint": "...", "url": "<không có key>", "params": {...}, "response": {...}}`.
- Cùng một bản ghi có thể xuất hiện nhiều lần (nhiều tag, chạy lại sau khi bị ngắt). Bước làm sạch khử trùng theo ID ([05](05_cleaning_pipeline.md), bước 3).
- Đọc bằng `so_recommender.collect.raw_store.iter_raw(root, endpoint)`.
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

Dữ liệu sạch **không có** ánh xạ câu trùng tới câu gốc và **không chia** train/val/test ([decisions.md](decisions.md), D13). Ánh xạ vẫn còn trong `closed_details.original_questions` của `data/raw/`.

## 3. Dữ liệu ghép sẵn cho mỗi câu hỏi: `data/clean/documents.json` và `documents.parquet`

Hai file chứa cùng các dòng và cùng các trường. `documents.parquet` là thư mục do Spark ghi, đọc được bằng `pandas.read_parquet`. Hiện xuất song song cho tới khi Hung chọn một định dạng (D13).

### Định dạng Hung yêu cầu (nhóm Messenger, 23/10/2026 20:37)

Một **mảng JSON**, mỗi phần tử là một câu hỏi. Ví dụ Hung gửi:

```json
[
  {
    "title": "Python async",
    "body": "How do I use async await? This is so ridiculouasd. ",
    "comments": ["Use asyncio.run"],
    "tags": ["python", "asyncio"]
  },
  {
    "title": "Async task error",
    "body": "My asyncio task fails and it's because of my cat",
    "comments": ["Wow you should cook him"],
    "tags": ["python", "asyncio"]
  }
]
```

### Các trường

| Trường | Kiểu | Nguồn trong dữ liệu sạch | Trạng thái |
|---|---|---|---|
| `title` | string | `questions.title` (đã giải mã HTML) | Hung yêu cầu |
| `body` | string | `questions.body_text` (đã bóc HTML) | Hung yêu cầu. Có giữ code không: xem câu hỏi mở |
| `comments` | list\<string\> | `comments.text` của câu hỏi, xếp theo thời gian, **đã bỏ comment làm lộ đáp án**. Rỗng `[]` nếu không có | Hung yêu cầu |
| `tags` | list\<string\> | `questions.tags` | Hung yêu cầu |
| `question_id` | int64 | `questions.question_id` | **ETL đề xuất thêm**: cần để nối với bảng khác và trích link nguồn |
| `answers` | list\<string\> | `answers.body_text`, xếp theo điểm | **ETL đề xuất thêm**, tùy chọn, **hiện chưa xuất**: chỉ cần nếu chạy cấu hình `C+Cm+A` |

Hai cấu hình văn bản: `C` dùng `title` + `body`, `C+Cm` dùng thêm `comments`.

## Câu hỏi mở

- [x] Định dạng lưu: **mảng JSON** như Hung gửi (23/10). Nếu file quá lớn thì có thể đổi sang JSONL (mỗi dòng một object).
- [ ] Giữ `documents.json`, `documents.parquet`, hay cả hai?
- [ ] Hung có đồng ý thêm `question_id` (và `answers` nếu cần) vào mỗi phần tử không?
- [ ] `comments` chỉ lấy comment của câu hỏi (theo ví dụ của Hung), hay lấy cả comment của các câu trả lời?
- [ ] `body` có giữ code (`body_code`) không, hay bỏ hẳn?

## Changelog

- **0.4** (05/11/2026): bỏ `duplicate_pairs`, `duplicate_groups`, `splits`, file `qrels.json` và trường `split` của `documents`. Thêm `documents.parquet` xuất song song với `documents.json` (D13). `questions.parquet` vẫn có thêm `closed_reason` và `warning_fields` như bản chạy hiện tại.
- **0.3** (24/10/2026): viết lại mục 3 theo định dạng Hung gửi ngày 23/10: mảng JSON gồm `title`, `body`, `comments`, `tags`, lưu ở `documents.json`. ETL đề xuất thêm `question_id`, `split`, `answers` và file nhãn `qrels.json`, đang chờ Hung xác nhận. Thay cho `documents.parquet` của bản 0.2.
- **0.2** (24/10/2026): mô tả cụ thể lớp raw theo bộ thu thập: thêm trường `endpoint`, liệt kê tên các thư mục endpoint, `url` không chứa key, raw có thể trùng bản ghi.
- **0.1** (23/10/2026): bản nháp đầu tiên.
