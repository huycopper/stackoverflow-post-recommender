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

### D7. Thiết kế bộ thu thập (24/10/2026)
- **Quyết định:** bộ thu thập chỉ dùng thư viện chuẩn của Python. Lấy mẫu theo thứ tự seed (câu vote cao) → linked (câu trùng trỏ tới seed) → background → originals → answers/comments. Lưu raw nguyên văn, data contract lên 0.2 cho lớp raw.
- **Lý do:** ai cũng chạy được mà không cần cài thêm. Đi từ các câu hỏi "kinh điển" cho ra nhiều cặp trùng với ít request. Chi tiết ở [03](03_data_source.md).
- **Người làm:** Huy Copper.

### D8. Không cắt câu trả lời và comment (24/10/2026)
- **Quyết định:** batch câu trả lời và comment được gom theo `answer_count`/`comment_count` (khoảng 500 mục mỗi batch) và lấy hết mọi trang. Thêm lệnh `repair` để lấy bù dữ liệu cũ bị thiếu.
- **Lý do:** cách cũ (100 ID, tối đa 5 trang) làm mẫu ngày 24/10 chỉ có 4.120 trên 9.222 câu trả lời. Cấu hình `C+Cm` cần comment của câu trả lời đầy đủ, còn báo cáo cần số liệu đúng.
- **Người làm:** Huy Copper.

### D9. Định dạng đầu vào model (23/10/2026)
- **Quyết định:** dữ liệu đưa cho bên model là một **mảng JSON**, mỗi phần tử gồm `title`, `body`, `comments` (danh sách chuỗi) và `tags` (danh sách chuỗi). Ghi trong data contract 0.3 ([04](04_data_contract.md), mục 3).
- **Lý do:** bên model cần một định dạng thống nhất để mỗi bên làm một phần ("thống nhất format data dùng cho model xong mỗi bên làm 1 thành phần").
- **Người chốt:** Hung (nhóm Messenger, 23/10/2026 20:37). ETL đề xuất thêm `question_id`, `split`, `answers` và file nhãn `qrels.json`, đang chờ Hung xác nhận.

### D10. Thu thập càng nhiều càng tốt, chạy tự động mỗi ngày (25/10/2026)
- **Quyết định:** tăng `seed_pages_per_tag` lên 100 và chạy bộ thu thập lúc 22:00 mỗi ngày bằng Task Scheduler trên máy Huy Copper ([03](03_data_source.md#chạy-tự-động-mỗi-ngày)). Việc làm sạch để sau, khi Huy Copper và Nguyễn Huy đã xem dữ liệu và tìm insight.
- **Lý do:** Hung chưa biết cần bao nhiêu dữ liệu, và đề xuất "chạy crawl tự động, cho hết data thô vào 1 chỗ rồi viết code xử lý song song". Quota giới hạn 10.000 request/ngày nên phải chạy qua nhiều ngày.
- **Người chốt:** Huy Copper, theo đề xuất của Hung.

### D11. Dừng thu thập, chuyển sang khám phá dữ liệu (26/10/2026)
- **Quyết định:** dừng ở 100 trang seed (93.704 câu hỏi, 23.470 cặp trùng) và tắt lịch 22:00 (Disabled, chưa xóa). Xuất dữ liệu ra `data/flat/*.parquet` và một file Excel thống kê kèm mẫu, để Huy Copper và Nguyễn Huy xem rồi thống nhất các bước làm sạch.
- **Lý do:** dữ liệu đã đủ cho đề tài, với khoảng 20 nghìn câu trùng làm query. Các bước làm sạch cần được chọn dựa trên insight từ dữ liệu thật ([05](05_cleaning_pipeline.md)).
- **Người chốt:** Huy Copper.

### D12. Nguyễn Huy phụ trách khám phá dữ liệu và làm sạch (26/10/2026)
- **Quyết định:** từ 26/10, Nguyễn Huy làm tiếp phần xem dữ liệu, tìm insight, chốt và cài đặt các bước làm sạch ([05](05_cleaning_pipeline.md)). Đầu vào là `data/flat/*.parquet` và `data/exports/explore_20261026.xlsx` từ D11.
- **Lý do:** Huy Copper đã làm xong phần thu thập và xuất dữ liệu. Nguyễn Huy nhận làm tiếp phần làm sạch.
- **Người chốt:** Nguyễn Huy và Huy Copper.

### D13. Lấy thêm bảng tag đồng nghĩa (29/10/2026)
- **Quyết định:** thêm bước `tag_synonyms` vào bộ thu thập, lấy **toàn bộ** bảng tag đồng nghĩa của Stack Overflow (5.332 cặp `from_tag → to_tag`, 54 request). Xuất thành `data/flat/tag_synonyms.parquet` và sheet "Tag đồng nghĩa" trong file Excel explore.
- **Lý do:** Nguyễn Huy đề xuất dùng bảng này để quy tag về tag chính. Lấy bảng rất rẻ, và hóa ra cần thật: dữ liệu vẫn còn 157 tag đồng nghĩa trên 2.290 câu hỏi (2,4%), ví dụ `selenium` (1.233 câu), dù trước đó tưởng Stack Overflow đã đổi hết ([03](03_data_source.md#các-endpoint-đang-dùng)). Hai cấu hình `C` và `C+Cm` chỉ dùng văn bản nên không bị ảnh hưởng. Lấy toàn bộ bảng thay vì chỉ lấy theo tag trong dữ liệu, vì tốn số request tương đương mà bảng lại đầy đủ.
- **Người chốt:** Huy Copper.

### D14. Thu thập thêm: 200 trang seed (29/10/2026)
- **Quyết định:** tăng `seed_pages_per_tag` từ 100 lên 200 (thêm 10.000 câu hỏi kinh điển cùng các câu liên kết tới chúng) và chạy tiếp bộ thu thập. Thay thế phần "dừng thu thập" của D11.
- **Lý do:** dự phòng trường hợp bước làm sạch loại bỏ nhiều dòng. Nguyễn Huy đề xuất "crawl hết các row" của các bảng. Lấy toàn bộ tag `python` (khoảng 2,2 triệu câu) thì cần khoảng 2 tháng quota, nên chọn mức gấp đôi, mất khoảng 1,5 ngày quota (100 trang trước tốn 13.157 request cho 93.704 câu). Seed sau trang 100 ít "kinh điển" hơn, nên số câu trùng tăng chậm hơn số câu hỏi.
- **Người chốt:** Huy Copper.

## Câu hỏi mở

| # | Câu hỏi | Ai chốt | Trạng thái |
|---|---|---|---|
| Q1 | Báo TA việc đổi nguồn sang Stack Overflow, Stack Overflow có tính là "social media" không | ? | Chưa hỏi lại |
| Q2 | Lưu trữ: Python + Parquet/SQL, hay lakehouse/Spark | Nguyễn Huy | Đang cân nhắc. Đề xuất Python ([06](06_architecture.md#lưu-trữ)) |
| Q3 | Phạm vi tag: `python`, hay thêm `pandas`, hay tag khác | ETL | Chỉ `python`. 10 trang seed (24/10), rồi tăng lên 100 trang (25/10, D10), rồi 200 trang (29/10, D14). Muốn thêm tag thì thêm vào `config/collect.toml`, lịch hằng ngày sẽ lấy tiếp |
| Q4 | Data contract lên 1.0 | ETL + Hung | Hung đã gửi định dạng (D9). Còn chờ Hung trả lời các trường bổ sung và cách lưu nhãn ([04](04_data_contract.md#câu-hỏi-mở-cần-chốt-với-bên-model)) |
| Q5 | Ai làm phần "Training + viết báo cáo" | Nam, Hoàng | Chưa chọn |
| Q6 | Có fine-tune model không | Hung | Chưa chốt ([07](07_modeling_eval.md)) |
