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

## Các endpoint dự kiến dùng

| Mục đích | Endpoint |
|---|---|
| Lấy câu hỏi theo tag | `GET /questions?tagged=python&sort=votes&filter=…` |
| Chi tiết câu hỏi theo ID (tối đa 100 ID mỗi lần) | `GET /questions/{ids}` |
| Câu trả lời | `GET /questions/{ids}/answers` |
| Comment của câu hỏi | `GET /questions/{ids}/comments` |
| Comment của câu trả lời | `GET /answers/{ids}/comments` |
| Câu hỏi liên kết hoặc trùng | `GET /questions/{ids}/linked` |

Lấy quan hệ trùng:

- Câu hỏi bị đóng vì trùng có `closed_reason = "Duplicate"`.
- Trường `closed_details.original_questions` liệt kê các câu gốc. Trường này cần được đưa vào filter.
- `/questions/{ids}/linked` trả về các câu hỏi liên kết tới, trong đó có những câu đã đóng vì trùng.

Hai cách trên cần đối chiếu với nhau khi viết bộ thu thập, rồi ghi lại cách chốt vào file này.

**Mẹo tiết kiệm quota:** tạo **filter tùy chỉnh** (`/filters/create`) để lấy luôn body, câu trả lời và comment trong cùng một response, thay vì gọi riêng từng endpoint.

## Quy tắc khi gọi API

- Đọc `quota_remaining` trong mỗi response và dừng khi còn dưới ngưỡng (ví dụ 20).
- Nếu response có trường `backoff`, **phải chờ đủ số giây đó** trước khi gọi lại endpoint đó.
- Có độ trễ giữa các request (khoảng 1 giây) và timeout cho mỗi request.
- Lưu **nguyên văn response** vào `data/raw/` (JSONL nén gzip, kèm thời điểm gọi và URL) để có thể chạy lại bước làm sạch mà không tốn quota.
- Bộ thu thập phải **chạy tiếp được** khi bị dừng giữa chừng: ghi lại trang hoặc ID đã lấy xong.

## Chiến lược lấy mẫu (đề xuất, chưa chốt)

1. **Câu hỏi trùng:** các câu hỏi đã đóng vì trùng trong tag đã chọn. Đây là các query.
2. **Câu hỏi gốc:** các câu được những câu trên trỏ tới. Đây là các câu liên quan.
3. **Câu hỏi nền:** các câu hỏi thường cùng tag, dùng làm câu không liên quan và làm kho tìm kiếm thực tế hơn.

Với mỗi câu hỏi, lấy thêm câu trả lời và comment của cả câu hỏi lẫn câu trả lời.

Ước lượng số request: một trang lấy được 100 câu hỏi. Với key 10.000 request/ngày, lấy vài chục nghìn câu hỏi kèm comment và câu trả lời mất khoảng 1–2 ngày.

## Bản quyền

Nội dung Stack Overflow được cấp phép theo **CC BY-SA**. Khi trích ví dụ trong báo cáo hoặc slide cần ghi nguồn (link câu hỏi). Ghi chú này vào phần "Khó khăn và đạo đức dữ liệu" của báo cáo.
