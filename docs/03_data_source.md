# 03. Nguồn dữ liệu: API Stack Exchange

## Vì sao dùng API (tóm tắt)

- Scrape trực tiếp `stackoverflow.com` **bị Cloudflare chặn**. Nhóm quyết định **không lách** cơ chế chống bot (D5 trong [decisions.md](decisions.md)).
- TA xác nhận gọi API vẫn được tính là bước thu thập dữ liệu ([02](02_course_requirements.md)).
- Dữ liệu từ API vẫn **cần làm sạch nhiều**: body là HTML thô, có code, ký tự bị mã hóa, comment làm lộ đáp án… Xem [05_cleaning_pipeline.md](05_cleaning_pipeline.md).
- **Không dùng** Data Dump hoặc SEDE (data.stackexchange.com) làm nguồn chính, vì đó là dữ liệu đã chuẩn bị sẵn và không có bước thu thập.

## Thông tin chung

| Mục | Giá trị |
|---|---|
| Base URL | `https://api.stackexchange.com/2.3` |
| Tham số site | `site=stackoverflow` |
| Quota không có key | 300 request/ngày/IP |
| Quota có key | 10.000 request/ngày. Đăng ký app miễn phí tại https://stackapps.com/apps/oauth/register |
| Số bản ghi mỗi trang | `pagesize` tối đa 100 |
| Định dạng ngày | Unix epoch (giây), cần đổi sang UTC timestamp |
| Body | Chỉ có khi dùng `filter=withbody` hoặc filter tùy chỉnh. Nội dung là **HTML** |

Key đặt trong biến môi trường `STACKEXCHANGE_KEY` (file `.env`, **không commit**).

## Các endpoint đang dùng

Code nằm ở `src/so_recommender/collect/`. Mỗi endpoint ghi raw vào một thư mục riêng trong `data/raw/`.

| Bước | Endpoint | Thư mục raw |
|---|---|---|
| `filter` | `GET /filters/create` (base `withbody` + các trường thêm) | `filters/` |
| `seed`, `background` | `GET /questions?tagged=…&sort=…` | `questions/` |
| `linked` | `GET /questions/{ids}/linked` | `questions_linked/` |
| `originals` | `GET /questions/{ids}` | `questions_by_id/` |
| `answers` | `GET /questions/{ids}/answers` | `answers/` |
| `question_comments` | `GET /questions/{ids}/comments` | `question_comments/` |
| `answer_comments` | `GET /answers/{ids}/comments` | `answer_comments/` |

`{ids}` là tối đa 100 ID nối bằng `;`, mỗi lần lấy tối đa 100 bản ghi một trang.

**Filter tùy chỉnh** = `withbody` + `question.closed_details`, `question.closed_date`, `question.closed_reason`, `question.comment_count`, `question.answer_count`, `question.link`, `answer.comment_count`, `comment.post_type`. Mã filter được tạo một lần rồi lưu trong state.

Lấy quan hệ trùng (đã kiểm tra với API thật ngày 23/10/2026):

- Câu hỏi bị đóng vì trùng có `closed_reason = "Duplicate"`.
- `closed_details.original_questions` liệt kê các câu gốc. Ví dụ: câu 79904105 có câu gốc là 38987.
- `/questions/{id}/linked` của một câu hỏi phổ biến có khoảng 16–18% là câu đã đóng vì trùng. Câu 38987 có 453 câu liên kết tới.

Comment và câu trả lời được lấy qua endpoint riêng, **không** nhúng vào filter của `/questions`. Lý do: cách này chắc chắn lấy đủ và có phân trang rõ ràng. Câu hỏi có `answer_count = 0` hoặc `comment_count = 0` được bỏ qua để tiết kiệm request.

## Quy tắc khi gọi API (đã cài trong `client.py`)

- Đọc `quota_remaining` trong mỗi response và **dừng khi còn dưới `min_quota_remaining`** (mặc định 50).
- Nếu response có trường `backoff`, **chờ số giây đó cộng thêm 2 giây** trước request kế tiếp. Chờ đúng bằng `backoff` vẫn bị API báo vi phạm (đã gặp ngày 24/10). Client áp mức chờ này cho mọi endpoint cho chắc.
- Mỗi request cách nhau ít nhất `request_delay_seconds` (1 giây), có timeout.
- Bị throttle (`error_id` 502) hoặc HTTP 429: chờ đúng số giây API báo. Nếu API không báo thì chờ tăng dần 60 → 120 → 240 giây. Thử 3 lần vẫn bị chặn thì **dừng và lưu tiến độ**.
- Lưu **nguyên văn response** vào `data/raw/`, kèm thời điểm gọi và URL **không chứa key**. Nhờ vậy chạy lại bước làm sạch không tốn quota.
- Tiến độ lưu ở `data/collect_state.json` sau mỗi trang hoặc mỗi batch. Chạy lại lệnh cũ là tiếp tục đúng chỗ dừng.

### Bài học: đừng gọi dồn dập

Ngày 23/10/2026, vài request thử gọi `/questions/{ids}/linked` liên tiếp nhau, kèm các lần thử lại mỗi 30 giây. Kết quả là API trả `throttle_violation: Violation of backoff parameter`, rồi tới **HTTP 429 `error code: 1015`**: Cloudflare chặn tạm thời theo IP. Nếu gặp lại:

- **Không** gọi thử liên tục bằng script riêng. Để client tự chờ, hoặc đợi khoảng 30–60 phút rồi chạy lại. Lần này lệnh chặn của Cloudflare hết sau khoảng 10 phút.
- Request bị timeout vẫn có thể đã được server xử lý, kèm một `backoff` mà mình không nhận được. Vì vậy client chờ ít nhất 30 giây trước khi thử lại.
- Mỗi người chỉ chạy **một** bộ thu thập tại một thời điểm, trên một IP.

## Chiến lược lấy mẫu (đã cài, chỉnh trong `config/collect.toml`)

1. **Seed:** `seed_pages_per_tag` trang câu hỏi được vote cao nhất của mỗi tag. Phần lớn là câu "kinh điển", có nhiều câu khác trùng với nó.
2. **Linked:** các câu hỏi liên kết tới seed, tối đa `linked_pages_per_batch` trang cho mỗi batch `linked_batch_size` seed (mặc định 10). Batch nhỏ vì mỗi seed có hàng trăm câu liên kết: gửi 100 seed trong một request thì API bị timeout, rồi báo vi phạm backoff. Câu nào đã đóng vì trùng thì cho ra một hoặc nhiều cặp (câu trùng, câu gốc). Đây là các **query** có nhãn.
3. **Background:** `background_pages_per_tag` trang câu hỏi thường cùng tag (`sort=activity`). Dùng làm câu không liên quan, để kho tìm kiếm thực tế hơn.
4. **Originals:** lấy thêm những câu gốc chưa có, tối đa `original_rounds` vòng để xử lý chuỗi trùng. Câu đã bị xóa được ghi nhận vào `unavailable_question_ids` để không hỏi lại.
5. **Answers và comments** của mọi câu hỏi đã lấy, và comment của mọi câu trả lời.
   - ID được **gom batch theo số lượng mục** (`answer_count` hoặc `comment_count` do API báo), mỗi batch khoảng `items_per_batch` mục (mặc định 500, tức 5 trang). Sau đó lấy **hết mọi trang** của batch.
   - `max_pages_per_batch` (50) chỉ là lưới an toàn. Nếu chạm giới hạn này, ID của batch đó được ghi vào `truncated_ids` trong state.
   - Trước 24/10 mỗi batch luôn có 100 ID và chỉ lấy tối đa 5 trang. Cách đó làm **mất khoảng 55% câu trả lời** của các câu hỏi kinh điển, vốn có tới 60–87 câu trả lời mỗi câu. Nếu dữ liệu cũ bị thiếu, chạy `repair` rồi `run` lại để lấy bù (xem README).

Ước lượng: một trang lấy được 100 câu hỏi. Mỗi 100 câu hỏi tốn khoảng 10–20 request cho câu trả lời và comment. Với key 10.000 request/ngày, lấy được vài chục nghìn câu hỏi trong 1–2 ngày.

Số liệu thật: lần chạy 24–25/10 với 10 trang seed (1.000 seed) tốn 2.185 request và cho 10.011 câu hỏi, 2.972 cặp trùng.

## Thu thập càng nhiều càng tốt (từ 25/10/2026)

Hung chưa chốt cần bao nhiêu dữ liệu, nên tạm thời nhóm **thu thập càng nhiều càng tốt** (D10):

- `seed_pages_per_tag = 100` (10.000 seed). Mỗi ngày bộ thu thập chạy tới khi gần hết quota thì dừng, hôm sau chạy tiếp. Dự kiến mất khoảng 3–4 ngày, được khoảng 100 nghìn câu hỏi và khoảng 600 MB raw.
- Các trang seed càng về sau thì câu hỏi càng ít "kinh điển", nên mỗi seed cho ít câu trùng hơn.
- Việc làm sạch **chưa làm**. Huy Copper và Nguyễn Huy sẽ xem dữ liệu, tìm insight trước, rồi mới thống nhất cần xử lý những gì.

## Chạy tự động mỗi ngày

`scripts/collect_daily.ps1` chạy bộ thu thập với `config/collect.toml` và ghi log vào `data/logs/`. Trên máy Huy Copper, script này được đặt lịch chạy 22:00 mỗi ngày (tạo ngày 25/10/2026). Tạo lịch giống vậy trên máy Windows khác (PowerShell, chạy dưới tài khoản của mình):

```powershell
$repo = "<đường dẫn tới repo>"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -WorkingDirectory $repo `
  -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$repo\scripts\collect_daily.ps1`""
$trigger = New-ScheduledTaskTrigger -Daily -At "22:00"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 20)
Register-ScheduledTask -TaskName "SO Recommender - daily collect" -Action $action -Trigger $trigger -Settings $settings
```

- Lịch chỉ chạy khi người dùng đang đăng nhập và máy không ngủ. Nếu lỡ giờ thì chạy bù ngay khi có thể (`-StartWhenAvailable`).
- Khóa `data/collect_state.lock` đảm bảo lịch và lần chạy tay không chạy chồng lên nhau.
- **Chỉ một máy được chạy bộ thu thập cho mỗi bộ dữ liệu.** Quota tính theo key và IP, và state nằm trên máy đó.

## Bản quyền

Nội dung Stack Overflow được cấp phép theo **CC BY-SA**. Khi trích ví dụ trong báo cáo hoặc slide cần ghi nguồn (link câu hỏi). Ghi chú này vào phần "Khó khăn và đạo đức dữ liệu" của báo cáo.
