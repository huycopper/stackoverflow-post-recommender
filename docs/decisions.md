# Nhật ký quyết định

Mỗi quyết định ghi: **ngày, quyết định, lý do, người chốt**. Không xóa mục cũ. Nếu thay đổi thì thêm mục mới ghi "thay thế Dx".

## Đã chốt

### D1. Đề tài: gợi ý bài viết dựa trên nội dung và comment (14/10/2026)
- **Quyết định:** làm hệ thống gợi ý top-K bài viết dùng nội dung và comment. Đã đăng ký qua form Project Registration DS ([01](01_project_brief.md)).
- **Lý do:** có câu hỏi nghiên cứu rõ ràng (comment có giúp ích không), có thể đánh giá định lượng, và bao được các bài giảng từ crawl tới evaluation.
- **Người đề xuất:** Hung. Ý tưởng recommender system ban đầu là của Huy Copper (11/10). Cả nhóm đồng ý.

### D2. Nguồn dữ liệu: Stack Overflow thay cho Facebook/Reddit (14/10/2026)
- **Quyết định:** dùng Stack Overflow.
- **Lý do:** có sẵn quan hệ câu hỏi trùng để làm nhãn đúng. Subreddit chỉ là nhãn yếu, vì một subreddit có nhiều chủ đề, còn bài liên quan lại có thể nằm ở các subreddit khác nhau. Gán nhãn bằng LLM thì tốn chi phí.
- **Người đề xuất:** Nguyễn Huy. Hung đồng ý.

### D3. Các câu trả lời của TA (16/10/2026)
- Pháp lý không phải tiêu chí chấm. Cách thu thập nào cũng được. **Bắt buộc có bước làm sạch thật sự**, nếu không sẽ bị trừ khoảng 20%. Khi trình bày phải nêu khó khăn với dữ liệu. Chi tiết ở [02](02_course_requirements.md).

### D4. Phân công theo tỉ lệ 2 – 1 – 2 (17/10/2026)
- **Quyết định:** 2 người ETL kiêm EDA, 1 người nghiên cứu và viết code model, 2 người training và viết báo cáo. Xem [08](08_team_workflow.md).
- **Lý do (Hung):** có AI hỗ trợ thì khối lượng của 1 người làm model tương đương 2 người làm ETL. Training tốn thời gian vì phải treo máy rồi mới đọc kết quả và sửa.

### D5. Lấy dữ liệu qua API chính thức của Stack Exchange, không lách chống bot (19/10/2026)
- **Quyết định:** dùng `api.stackexchange.com`. Không scrape HTML và không bypass Cloudflare bằng giả cookie hay fingerprint.
- **Lý do:** stackoverflow.com bị Cloudflare chặn. Lách chống bot vừa khó vừa không nên làm. TA xác nhận gọi API được tính là bước thu thập. Dữ liệu API vẫn là HTML thô nên vẫn đủ việc làm sạch ([05](05_cleaning_pipeline.md)).
- **Người đề xuất:** Huy Copper. Hung đồng ý.

### D6. Repo chung mới (23/10/2026)
- **Quyết định:** dùng repo `huycopper/stackoverflow-post-recommender` làm repo chung, bắt đầu từ đầu. Repo `44444huy/DataScience_20261` không dùng nữa.
- **Người chốt:** Huy Copper.

## Câu hỏi mở

| # | Câu hỏi | Ai chốt | Trạng thái |
|---|---|---|---|
| Q1 | Báo TA việc đổi nguồn sang Stack Overflow, Stack Overflow có tính là "social media" không | ? | Chưa hỏi lại |
| Q2 | Lưu trữ: Python + Parquet/SQL, hay lakehouse/Spark | Nguyễn Huy | Đang cân nhắc. Đề xuất Python ([06](06_architecture.md#lưu-trữ)) |
| Q3 | Phạm vi tag: `python`, hay thêm `pandas`, hay tag khác | ETL | Chưa chốt |
| Q4 | Data contract 0.1 lên 1.0 | ETL + Hung | Chờ dữ liệu mẫu |
| Q5 | Ai làm phần "Training + viết báo cáo" | Nam, Hoàng | Chưa chọn |
| Q6 | Có fine-tune model không | Hung | Chưa chốt ([07](07_modeling_eval.md)) |
