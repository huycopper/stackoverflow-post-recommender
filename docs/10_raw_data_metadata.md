# 10. Mô tả dữ liệu thô (`data/raw/`)

File này giải thích **từng thư mục, từng trường** của dữ liệu thô lấy từ API Stack Exchange. Số liệu được đo trực tiếp trên bộ dữ liệu đóng gói ngày 29/10/2026 (`so_raw_jsonl_20261029.zip`), không lấy từ tài liệu API.

> **Tóm tắt.** Dữ liệu thô là các **response nguyên văn** của API, mỗi dòng là một lần gọi API, chứa tối đa 100 bản ghi. Cùng một bản ghi có thể xuất hiện nhiều lần, nên phải khử trùng. Sau khi khử trùng có **93.704 câu hỏi**, **257.960 câu trả lời**, **647.383 comment** (254.893 của câu hỏi và 392.490 của câu trả lời) và **23.470 cặp câu hỏi trùng**.

## 1. Cấu trúc thư mục

```
data/raw/
  questions/          câu hỏi seed (vote cao nhất) và background, lấy theo tag
  questions_linked/   câu hỏi liên kết tới seed. Câu bị đóng vì trùng nằm chủ yếu ở đây
  questions_by_id/    câu gốc lấy bổ sung theo ID (câu gốc chưa có trong 2 thư mục trên)
  answers/            câu trả lời của mọi câu hỏi
  question_comments/  comment dưới câu hỏi
  answer_comments/    comment dưới câu trả lời
  tag_synonyms/       bảng tag đồng nghĩa của toàn bộ Stack Overflow
  filters/            filter API đã dùng (danh sách trường được bật)
data/raw_manifest.json  thống kê số file, số response, số item của từng thư mục
```

Tên file là **ngày lấy dữ liệu theo giờ UTC**: `YYYYMMDD.jsonl.gz`. Mỗi file là JSON Lines nén gzip, mã hóa UTF-8.

| Thư mục | Số item thô | Khóa duy nhất | Số bản ghi sau khử trùng |
|---|---:|---|---:|
| `questions` | 10.100 | `question_id` | (gộp với 2 thư mục dưới) |
| `questions_linked` | 260.034 | `question_id` | (gộp) |
| `questions_by_id` | 2.308 | `question_id` | (gộp) |
| **Tổng câu hỏi** | 272.442 | `question_id` | **93.704** |
| `answers` | 257.960 | `answer_id` | 257.960 |
| `question_comments` | 254.893 | `comment_id` | 254.893 |
| `answer_comments` | 392.590 | `comment_id` | 392.490 |
| `tag_synonyms` | 5.332 | `from_tag` | 5.332 |

## 2. Một dòng trong file là gì?

Mỗi dòng là **một response**, không phải một bản ghi:

```json
{
  "fetched_at": "2026-10-24T10:00:00+00:00",
  "endpoint": "answers",
  "url": "https://api.stackexchange.com/2.3/questions/38987;.../answers?...",
  "params": { "...": "..." },
  "response": {
    "items": [ { "...một bản ghi...": 1 }, "...tối đa 100 bản ghi..." ],
    "has_more": true,
    "quota_max": 10000,
    "quota_remaining": 9000,
    "backoff": 10
  }
}
```

| Trường | Ý nghĩa |
|---|---|
| `fetched_at` | Thời điểm gọi API (UTC). **Dùng để chọn bản mới nhất khi bị trùng** |
| `endpoint` | Tên thư mục chứa dòng này |
| `url`, `params` | URL và tham số đã gọi. Không chứa API key |
| `response.items` | Danh sách bản ghi. Đây là phần dữ liệu cần dùng |
| `response.has_more` | Còn trang tiếp theo không |
| `response.quota_remaining` | Số request còn lại trong ngày |
| `response.backoff` | Chỉ xuất hiện khi API yêu cầu chờ (số giây) |

Đọc dữ liệu:

```python
import gzip, json
from pathlib import Path

for path in sorted(Path("data/raw/questions_linked").glob("*.jsonl.gz")):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            for q in rec["response"]["items"]:
                ...  # q["question_id"], q["title"], q["body"], ...
```

## 3. Quy ước chung cho mọi trường

- **Ngày giờ** (`creation_date`, `closed_date`…) là **số Unix, tính bằng giây, múi giờ UTC**. Ví dụ `1773085962`. Cần đổi sang timestamp trước khi dùng.
- **`body`, `title`, `display_name`** là chuỗi có **HTML escape**: `&quot;` là dấu `"`, `&#39;` là dấu `'`, `&amp;` là dấu `&`. `body` còn chứa thẻ HTML thật (`<p>`, `<pre><code>`, `<a>`…).
- **`owner`** là thông tin người đăng. Một số bài **không có** `owner.user_id` (khoảng 2,4% câu hỏi): tài khoản đã bị xóa hoặc chưa đăng ký. Khi đó chỉ còn `owner.display_name` và `owner.user_type`.
- **Trường tùy chọn:** nếu một bài không có giá trị (ví dụ chưa từng được sửa) thì API **bỏ hẳn trường** chứ không trả `null`. Cột "Có giá trị" trong bảng dưới cho biết tỉ lệ bản ghi có trường đó.
- **Bản quyền:** nội dung thuộc giấy phép CC BY-SA (trường `content_license` ghi rõ phiên bản). Khi trích dẫn trong báo cáo phải ghi nguồn.
- **Dữ liệu cá nhân:** các trường `owner.*`, `reply_to_user.*`, `closed_details.by_users[]` chứa tên hiển thị, ảnh đại diện và đường dẫn hồ sơ của người dùng thật. Đây là dữ liệu công khai nhưng **không cần cho mô hình**. Không đưa các trường này vào kho văn bản, bảng thống kê hay báo cáo.

## 4. Bảng câu hỏi (`questions`, `questions_linked`, `questions_by_id`)

Cả 3 thư mục có **cùng cấu trúc**, chỉ khác nguồn:

| Thư mục | Nguồn gốc | Số bài đóng vì trùng |
|---|---|---|
| `questions` | 100 trang đầu của tag `python` theo vote (seed) và 1 trang theo hoạt động gần đây (background) | 12,8% |
| `questions_linked` | Câu hỏi có link tới seed, gọi theo nhóm 10 seed, sắp theo `activity`, tối đa 3 trang. **Không phải mọi câu liên kết**, xem mục 8 điểm 1 | 24,4% |
| `questions_by_id` | Câu gốc mà không thuộc 2 nhóm trên | 10,1% |

Tỉ lệ ở cột "Có giá trị" dưới đây đo trên thư mục `questions_linked` (260.034 item), là thư mục lớn nhất.

### Các trường chính (dùng được ngay)

| Trường | Kiểu | Có giá trị | Ý nghĩa | Dự án có dùng? |
|---|---|---:|---|---|
| `question_id` | số nguyên | 100% | Mã câu hỏi, **khóa chính** | Có |
| `title` | chuỗi | 100% | Tiêu đề, có HTML escape | Có |
| `body` | chuỗi | 100% | Nội dung, là HTML (có `<pre><code>`) | Có |
| `tags` | danh sách chuỗi | 100% | Tag, tối đa 5, trung bình 3 | Có |
| `score` | số nguyên | 100% | Điểm = vote lên trừ vote xuống. Có thể âm | Có |
| `view_count` | số nguyên | 100% | Số lượt xem | Có |
| `answer_count` | số nguyên | 100% | Số câu trả lời theo API | Có |
| `comment_count` | số nguyên | 100% | Số comment **theo API, không đáng tin**, xem mục 8 | Có (cần tính lại) |
| `creation_date` | số Unix | 100% | Ngày đăng | Có |
| `is_answered` | bool | 100% | Có câu trả lời được chấp nhận hoặc điểm cao | Không |
| `link` | chuỗi | 100% | URL câu hỏi | Có |
| `accepted_answer_id` | số nguyên | 54% | Mã câu trả lời được chấp nhận. Không có nghĩa là chưa trả lời | Có |
| `last_activity_date` | số Unix | 100% | Lần hoạt động cuối (sửa, trả lời, comment) | Không |
| `last_edit_date` | số Unix | 66% | Lần sửa nội dung cuối. Thiếu nếu chưa sửa lần nào | Không |
| `content_license` | chuỗi | 60% | Giấy phép, ví dụ `CC BY-SA 4.0`. Một phần bản ghi cũ không có | Không |

### Các trường về việc đóng câu hỏi (quan trọng nhất cho nhãn)

| Trường | Kiểu | Có giá trị | Ý nghĩa |
|---|---|---:|---|
| `closed_date` | số Unix | 24% | Thời điểm đóng. **Chỉ có khi bài đã bị đóng** |
| `closed_reason` | chuỗi | 24% | Lý do đóng. Giá trị: `Duplicate` (20.103 câu), `Not suitable for this site` (584), `Needs details or clarity` (332), `Needs more focus` (313), `Opinion-based` (209), `exact duplicate` (138), `not constructive` (53) |
| `closed_details.reason` | chuỗi | 24% | Giống `closed_reason` |
| `closed_details.description` | chuỗi | 24% | Câu giải thích hiển thị cho người dùng |
| `closed_details.original_questions[]` | danh sách | 23% | **Danh sách câu gốc** (chỉ có khi trùng). Mỗi phần tử có `question_id`, `title`, `answer_count`, `accepted_answer_id` |
| `closed_details.by_users[]` | danh sách | 24% | Người đã bỏ phiếu đóng. **Dữ liệu cá nhân, không dùng** |

**Cách lấy cặp trùng:** câu hỏi có `closed_reason == "Duplicate"` và mỗi `closed_details.original_questions[].question_id` tạo một cặp `(câu trùng → câu gốc)`. Một câu trùng có thể có nhiều câu gốc (2.756 câu).

### Các trường ít dùng

| Trường | Có giá trị | Ý nghĩa |
|---|---:|---|
| `protected_date` | 5% | Ngày bài bị bảo vệ (chỉ người đủ điểm mới trả lời được) |
| `locked_date` | 0,1% | Ngày bài bị khóa |
| `community_owned_date` | 0,2% | Ngày chuyển thành bài cộng đồng (wiki) |
| `migrated_from.*` | 0,1% | Thông tin nếu bài được chuyển từ site Stack Exchange khác (kèm toàn bộ thông tin site đó, rất dài) |
| `bounty_amount`, `bounty_closes_date` | gần 0 | Tiền thưởng cho câu trả lời |
| `owner.*` | 98% | Người đăng: `user_id`, `reputation`, `accept_rate`, `display_name`, `link`, `profile_image`, `account_id`, `user_type` |

**`owner.user_type`** có 4 giá trị: `registered` (91.064 câu hỏi), `does_not_exist` (2.230, tài khoản đã xóa), `unregistered` (389), `moderator` (21).

## 5. Bảng câu trả lời (`answers`)

257.960 item. Khóa chính là `answer_id`.

| Trường | Kiểu | Có giá trị | Ý nghĩa |
|---|---|---:|---|
| `answer_id` | số nguyên | 100% | Mã câu trả lời |
| `question_id` | số nguyên | 100% | Câu hỏi mà câu trả lời này thuộc về. **Khóa ngoại** |
| `body` | chuỗi | 100% | Nội dung, là HTML (có thể có `<h2>`, `<a>`, `<pre><code>`) |
| `score` | số nguyên | 100% | Điểm vote |
| `is_accepted` | bool | 100% | Có phải câu trả lời được chấp nhận không |
| `comment_count` | số nguyên | 100% | Số comment theo API |
| `creation_date` | số Unix | 100% | Ngày đăng |
| `last_activity_date` | số Unix | 100% | Hoạt động cuối |
| `last_edit_date` | số Unix | 46% | Lần sửa cuối |
| `content_license` | chuỗi | 100% | Giấy phép |
| `community_owned_date` | số Unix | 1,1% | Ngày thành bài cộng đồng |
| `owner.*` | | 98,7% | Người đăng, giống mục 4 |
| `posted_by_collectives[]`, `recommendations[]` | | dưới 0,02% | Thông tin "Collectives" của Stack Overflow, không dùng |

Kiểm tra: không có câu trả lời nào trỏ tới câu hỏi không tồn tại trong dữ liệu. 3 câu hỏi có `answer_count` lệch với số câu trả lời lấy được.

## 6. Bảng comment (`question_comments`, `answer_comments`)

Hai thư mục có cùng cấu trúc. Khóa chính là `comment_id`. `answer_comments` có 392.590 item nhưng chỉ có 392.490 comment khác nhau (100 bản trùng).

| Trường | Kiểu | Có giá trị | Ý nghĩa |
|---|---|---:|---|
| `comment_id` | số nguyên | 100% | Mã comment |
| `post_id` | số nguyên | 100% | Mã bài cha. Là `question_id` nếu `post_type = "question"`, là `answer_id` nếu `post_type = "answer"` |
| `post_type` | chuỗi | 100% | `question` hoặc `answer` |
| `body` | chuỗi | 100% | Nội dung, là HTML ngắn (trung vị 111 ký tự, tối đa 1.708 ký tự) |
| `score` | số nguyên | 100% | Số vote cho comment |
| `creation_date` | số Unix | 100% | Ngày đăng |
| `edited` | bool | 100% | Đã bị sửa chưa |
| `content_license` | chuỗi | 100% | Giấy phép |
| `owner.*` | | 98% | Người comment |
| `reply_to_user.*` | | 24% | Người được trả lời (khi comment bắt đầu bằng `@tên`). Dữ liệu cá nhân, không dùng |

**Lưu ý:** comment dưới câu trả lời chỉ có `post_id` của câu trả lời. Muốn biết thuộc câu hỏi nào phải nối qua bảng `answers` (`answer_id` → `question_id`).

## 7. Bảng tag đồng nghĩa (`tag_synonyms`)

5.332 dòng. Cho biết tag nào được cộng đồng coi là cùng nghĩa với tag chính.

| Trường | Ý nghĩa |
|---|---|
| `from_tag` | Tag cũ hoặc cách viết khác. **Khóa chính** |
| `to_tag` | Tag chính cần đổi sang |
| `applied_count` | Số bài đã áp dụng |
| `creation_date` | Ngày tạo quan hệ |
| `last_applied_date` | Lần áp dụng cuối (thiếu ở 14% dòng) |

Ví dụ: `windows-forms` đổi thành `winforms`. Trong dữ liệu hiện tại, 2.290 câu hỏi còn mang 157 tag đồng nghĩa chưa đổi.

## 8. Các điểm cần chú ý trước khi dùng

| # | Vấn đề | Số liệu đo được | Cách xử lý |
|---|---|---|---|
| 1 | **Bản ghi trùng.** Một câu hỏi xuất hiện nhiều lần | 272.442 item thô cho 93.704 câu hỏi (trung bình 2,9 lần mỗi câu). Không có request nào bị gọi lặp lại. Nguyên nhân chính nằm ở `questions_linked`: trong 819 nhóm seed có đủ 3 trang, **trang 1, 2 và 3 trả về đúng cùng 100 câu hỏi**, dù URL có `page=1`, `page=2`, `page=3` và API vẫn báo `has_more = true`. Vì vậy mỗi nhóm 10 seed thực tế chỉ cho 100 câu khác nhau chứ không phải 300 | Khử trùng theo `question_id`, giữ bản có `fetched_at` mới nhất, vì bài có thể đổi trạng thái giữa hai lần lấy. Lưu ý thêm: số câu liên kết thật sự lấy được ít hơn nhiều so với lượng câu có link tới seed. Chưa rõ vì sao API lặp trang (chưa kiểm tra lại với API) |
| 2 | **Comment làm lộ đáp án** | Khoảng 36.567 comment của câu hỏi khớp một trong các mẫu "possible duplicate", "does this answer your question", "duplicate of" hoặc có link `/questions/<số>` | Lọc ở bước làm sạch. Số chính xác phụ thuộc vào mẫu lọc: README cũ đếm 14.986 với mẫu hẹp hơn |
| 3 | **`comment_count` sai** | 935 câu hỏi báo nhiều comment hơn số lấy được, 4 câu thì ngược lại | Tính lại từ comment thực tế |
| 4 | **Câu gốc bị thiếu** | 3 câu gốc đã bị xóa | Bỏ cặp tương ứng hoặc ghi nhận |
| 5 | **Thiếu comment** | 75,7% câu hỏi có comment. Với câu bị đóng vì trùng là 76,6% | Cấu hình `C+Cm` sẽ không khác `C` ở khoảng 1/4 số câu |
| 6 | **Nhóm trùng lệch mạnh** | 4.808 nhóm, trong đó 1 nhóm có 8.042 câu, nhóm lớn thứ hai chỉ 162 câu | Cần xem lại khi chia train/val/test theo nhóm |
| 7 | **Tag đồng nghĩa** | 2.290 câu mang 157 tag cần đổi | Đổi theo `tag_synonyms` nếu dùng tag |
| 8 | **Ngày tương lai** | Một số `last_activity_date` có giá trị năm 2026 vì dữ liệu lấy vào tháng 10/2026 | Không phải lỗi |

## 9. Thống kê nhanh của dữ liệu (sau khử trùng)

| Chỉ số | Giá trị |
|---|---|
| Số câu hỏi | 93.704 |
| Số câu đóng vì trùng (`Duplicate`) | 20.103 |
| Số cặp (trùng → gốc) | 23.470 |
| Số nhóm trùng (liên thông) | 4.808 |
| Độ dài body, bỏ HTML (ký tự) | trung vị 767, p90 2.372, tối đa 38.639 |
| Tỉ lệ bài có khối code | 82% |
| Điểm `score` | trung vị 1, trung bình 34,5, tối đa 27.546. 8.955 câu có điểm âm |
| Số tag khác nhau | 8.651. Phổ biến nhất: `python` (81.646), `python-3.x` (13.130), `pandas` (12.490) |
| Năm đăng nhiều nhất | 2020 (12.511 câu), 2021 (12.154), 2022 (11.400) |
| Tỉ lệ câu hỏi có ít nhất 1 câu trả lời | 86,9% |
| Số comment trên mỗi câu hỏi | trung bình 2,7, trung vị 2, tối đa 40 |

## 10. Liên quan

- Cách lấy dữ liệu: [03_data_source.md](03_data_source.md)
- Định dạng dữ liệu sạch dùng cho mô hình: [04_data_contract.md](04_data_contract.md)
- Các bước làm sạch: [05_cleaning_pipeline.md](05_cleaning_pipeline.md)
