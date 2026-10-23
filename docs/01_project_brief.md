# 01. Mô tả dự án

## Bài toán

Cho một câu hỏi Stack Overflow (gọi là **query**), hệ thống trả về **K câu hỏi liên quan nhất** trong một kho câu hỏi.

- **Loại bài toán học máy:** xếp hạng (ranking / retrieval).
- **Input:** một câu hỏi, gồm tiêu đề, nội dung, tag, comment, và có thể thêm câu trả lời.
- **Output:** danh sách K câu hỏi xếp theo độ liên quan giảm dần.
- **Kiểu dữ liệu:** văn bản (HTML có chứa code), metadata (tag, điểm, thời gian) và đồ thị quan hệ trùng giữa các câu hỏi.

## Câu hỏi nghiên cứu

> Thêm thông tin từ comment có cải thiện chất lượng gợi ý so với chỉ dùng nội dung bài viết không?

So sánh tối thiểu hai cấu hình trên cùng tập dữ liệu và cùng model:

| Cấu hình | Văn bản đưa vào model |
|---|---|
| `C` | Nội dung: tiêu đề + body |
| `C+Cm` | Nội dung + comment |

Có thể thêm `C+Cm+A` (thêm câu trả lời) nếu còn thời gian. Chi tiết ở [07_modeling_eval.md](07_modeling_eval.md).

## Nhãn đúng (ground truth)

Trên Stack Overflow, một câu hỏi có thể bị đóng là **duplicate** của một hoặc nhiều câu hỏi gốc. Với mỗi query là câu hỏi bị đóng vì trùng, các câu hỏi gốc của nó (và các câu khác cùng nhóm trùng) được coi là **liên quan**. Cách xây nhóm trùng xem [05_cleaning_pipeline.md](05_cleaning_pipeline.md), bước 4.

## Đánh giá

Precision@K, Recall@K, NDCG@K, với K ∈ {5, 10} (chốt lại ở [07_modeling_eval.md](07_modeling_eval.md)).

## Ứng dụng thực tế

- Gợi ý "câu hỏi liên quan" khi người dùng đọc một câu hỏi.
- Phát hiện câu hỏi trùng ngay khi người dùng đang đăng câu hỏi mới, giúp giảm câu hỏi lặp và tiết kiệm công kiểm duyệt.
- Kết quả về vai trò của comment áp dụng được cho các diễn đàn hỏi đáp và cộng đồng khác.

## Phạm vi

- **Nguồn:** Stack Overflow, lấy qua API chính thức của Stack Exchange ([03_data_source.md](03_data_source.md)).
- **Tag:** bắt đầu với `python` (có thể thêm `pandas`). Chưa chốt, xem câu hỏi mở trong [decisions.md](decisions.md).
- **Ngôn ngữ:** chỉ tiếng Anh.

**Không làm:** hệ thống chạy thời gian thực, giao diện người dùng phức tạp (chỉ cần demo đơn giản cho buổi thuyết trình), nhiều site Stack Exchange cùng lúc.

## Mô tả đã đăng ký (form Project Registration DS, 14/10/2026)

Tên đề tài: **Content- and Comment-Based Post Recommendation**

> We build a top-K post recommender that uses both post content and comments. The learning problem is a ranking task with input as a query post, and output as K most relevant posts. Our objective is to test whether adding comment information improves recommendation quality over using post content alone. Data is scraped from social media platforms via web scraping, then cleaned and converted into a standardized format. Posts and comments are represented as text features, and relevance is judged using topic labels and user interaction signals. We evaluate with Precision@K, Recall@K, and NDCG@K.

**Khác biệt so với kế hoạch hiện tại** (cần báo TA, xem [decisions.md](decisions.md)):

- Nguồn dữ liệu: "social media platforms via web scraping" đổi thành **Stack Overflow qua API chính thức**.
- Cách xác định liên quan: "topic labels and user interaction signals" đổi thành **quan hệ câu hỏi trùng**.
