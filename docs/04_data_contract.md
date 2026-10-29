# 04. Data contract

> **Version: 0.3 (DRAFT)**. Hung đã gửi định dạng đầu vào model mong muốn (23/10/2026, mục 3). ETL cần xác nhận với Hung các trường bổ sung ở mục 3, sau đó chốt thành 1.0.

Đây là **giao diện giữa ETL và bên model**. ETL cam kết xuất đúng định dạng này. Bên model chỉ đọc từ các bảng ở mục 2 và 3, không đọc dữ liệu thô.

Quy tắc thay đổi:

- Thêm trường mới không bắt buộc: tăng minor version (0.1 → 0.2).
- Đổi tên, đổi kiểu hoặc xóa trường: tăng major version, và cần cả ETL lẫn bên model duyệt PR.
- Mọi thay đổi đều ghi vào mục Changelog cuối file và thêm một mục vào [decisions.md](decisions.md).
- Trước bản 1.0 đây vẫn là bản nháp: được đổi tên hoặc đổi trường mà chỉ cần tăng minor version, miễn là ghi changelog.

## 1. Dữ liệu thô: `data/raw/`

- Response nguyên văn từ API, mỗi dòng một response: `data/raw/{endpoint}/{YYYYMMDD}.jsonl.gz` (ngày theo UTC).
- `endpoint` ∈ `filters`, `questions`, `questions_linked`, `questions_by_id`, `answers`, `question_comments`, `answer_comments`, `tag_synonyms`. Ý nghĩa từng loại xem [03](03_data_source.md#các-endpoint-đang-dùng).
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

## 3. Dữ liệu đưa vào model: `data/clean/documents.json`

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
| `question_id` | int64 | `questions.question_id` | **ETL đề xuất thêm**: cần để nối với nhãn đúng, chia dữ liệu và trích link nguồn |
| `split` | string | `splits.split` | **ETL đề xuất thêm**: `train`, `val`, `test` theo nhóm trùng |
| `answers` | list\<string\> | `answers.body_text`, xếp theo điểm | **ETL đề xuất thêm**, tùy chọn: chỉ cần nếu chạy cấu hình `C+Cm+A` |

Cấu hình thí nghiệm ([07](07_modeling_eval.md)): `C` dùng `title` + `body`, `C+Cm` dùng thêm `comments`.

### Nhãn đúng: `data/clean/qrels.json` (ETL đề xuất)

Mảng các query, tức các câu hỏi bị đóng vì trùng:

```json
[{"query_id": 79904105, "relevant_ids": [38987], "split": "test"}]
```

`relevant_ids` là các câu khác cùng nhóm trùng với query (`duplicate_groups`). Định dạng của Hung không có chỗ cho nhãn, nên cần một file riêng như thế này hoặc một cách khác mà Hung chọn.

## Câu hỏi mở cần chốt với bên model

- [x] Định dạng lưu: **mảng JSON** như Hung gửi (23/10). Nếu file quá lớn thì có thể đổi sang JSONL (mỗi dòng một object).
- [ ] Hung có đồng ý thêm `question_id`, `split` (và `answers` nếu cần) vào mỗi phần tử không?
- [ ] Nhãn đúng để ở file `qrels.json` như trên, hay Hung muốn cách khác?
- [ ] `comments` chỉ lấy comment của câu hỏi (theo ví dụ của Hung), hay lấy cả comment của các câu trả lời?
- [ ] `body` có giữ code (`body_code`) không, hay bỏ hẳn?
- [ ] Có cắt độ dài văn bản không (model dạng transformer giới hạn số token)?

## Changelog

- **0.3** (24/10/2026): viết lại mục 3 theo định dạng Hung gửi ngày 23/10: mảng JSON gồm `title`, `body`, `comments`, `tags`, lưu ở `documents.json`. ETL đề xuất thêm `question_id`, `split`, `answers` và file nhãn `qrels.json`, đang chờ Hung xác nhận. Thay cho `documents.parquet` của bản 0.2.
- **0.2** (24/10/2026): mô tả cụ thể lớp raw theo bộ thu thập: thêm trường `endpoint`, liệt kê tên các thư mục endpoint, `url` không chứa key, raw có thể trùng bản ghi.
- **0.1** (23/10/2026): bản nháp đầu tiên.
