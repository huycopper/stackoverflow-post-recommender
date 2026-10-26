# 09. Kế hoạch

Cập nhật lần cuối: **23/10/2026**. Ngày báo cáo tiến độ và báo cáo cuối **chưa có**. Khi có thì thêm vào đây và vào [02](02_course_requirements.md#mốc-thời-gian).

Đánh dấu `[x]` khi xong, ghi tên người nhận sau mỗi mục.

## Giai đoạn 0: Chuẩn bị (tuần 23/10)

- [x] Tạo repo chung và các docs context. (Huy Copper)
- [ ] Mời cả nhóm vào repo. (Huy Copper)
- [x] Đăng ký key StackApps (app 41381, key `api-collector` hết hạn khoảng 21/01/2027, lưu trong `.env` trên máy Huy Copper). (Huy Copper)
- [ ] Hỏi TA về việc đổi nguồn dữ liệu sang Stack Overflow, và Stack Overflow có tính là mạng xã hội không. (?)
- [ ] Chốt người cho phần "Training + viết báo cáo". (Nam, Hoàng)

## Giai đoạn 1: Thu thập dữ liệu

- [x] Bộ thu thập qua API: quota, backoff, chạy tiếp được khi dừng, lưu raw. (Huy Copper)
- [x] Lấy mẫu kèm câu trả lời, comment và quan hệ trùng (`config/collect_sample.toml`, 24/10), tổng cộng 403 request. (Huy Copper)
  - 1.210 câu hỏi, 308 cặp trùng.
  - 9.223 câu trả lời, đủ so với `answer_count`.
  - 20.893 comment: comment của câu trả lời đủ; comment của câu hỏi được 3.856 trên 4.157, vì 80 câu API không trả comment.
- [ ] Gửi mẫu cho bên model, chốt data contract lên **1.0**. (ETL + Hung)
  - [x] Hung gửi định dạng đầu vào model mong muốn (23/10): mảng JSON gồm `title`, `body`, `comments`, `tags`. Đã ghi vào data contract 0.3.
  - [ ] Hỏi Hung về các trường ETL đề xuất thêm (`question_id`, `split`, `answers`) và file nhãn `qrels.json`. (Huy Copper)
  - [ ] Xuất mẫu theo định dạng này rồi gửi Hung kiểm tra. (Huy Copper)
- [x] Lần thu thập đầy đủ đầu tiên (24–25/10, `config/collect.toml`: tag `python`, 10 trang seed). Tốn 2.185 request, dữ liệu 60 MB trong `data/raw/` trên máy Huy Copper, tóm tắt ở `data/exports/full_summary_20261025.json`. (Huy Copper)
  - **10.011 câu hỏi**: 1.000 seed, 100 background, còn lại là câu liên kết và câu gốc. 2.451 câu bị đóng vì trùng, ra **2.972 cặp trùng**, đủ cả câu gốc.
  - 50.271 câu trả lời: thiếu 1 câu so với `answer_count`, ở 2 câu hỏi.
  - Comment: 87.898 comment của câu trả lời (đủ). 29.460 trên 30.835 comment của câu hỏi, vì có 353 câu API không trả comment. 1.578 comment làm lộ đáp án, cần lọc.
  - 76% câu hỏi có comment. Trong các câu trùng, 1.750 trên 2.451 câu (71%) có comment.
  - Cả 100 batch `linked` đều chạm giới hạn 3 trang. Muốn thêm câu trùng thì tăng `seed_pages_per_tag` rồi chạy tiếp.
- [x] Thu thập càng nhiều càng tốt (D10): 100 trang seed, xong lúc 22:12 ngày 25/10 sau 3 lần chạy (13.103 request), dữ liệu 376 MB trong `data/raw/`, tóm tắt ở `data/exports/full_summary_20261026.json`. (Huy Copper)
  - **93.704 câu hỏi**: 10.000 seed, 100 background, còn lại là câu liên kết và câu gốc. 20.103 câu bị đóng vì trùng, ra **23.470 cặp trùng**. Thiếu 3 câu gốc vì đã bị xóa.
  - 257.960 câu trả lời: thiếu 1 câu so với `answer_count`.
  - Comment: 392.490 comment của câu trả lời (đủ). 254.893 trên 258.630 comment của câu hỏi, vì có 935 câu API không trả comment. 14.986 comment làm lộ đáp án, cần lọc.
  - 76% câu hỏi có comment. Trong các câu trùng, 15.402 trên 20.103 câu (77%) có comment.
  - Lịch 22:00 vẫn bật. Với cấu hình hiện tại thì không còn gì để lấy, nên mỗi lần chạy sẽ xong ngay. Muốn lấy thêm thì tăng `seed_pages_per_tag` hoặc thêm tag.
- [ ] Huy Copper và Nguyễn Huy xem dữ liệu, tìm insight, chốt các bước làm sạch. (ETL)

## Giai đoạn 2: Làm sạch, tích hợp, EDA

- [ ] 6 bước làm sạch và `cleaning_stats.json`. (Nguyễn Huy)
- [ ] Nhóm trùng và chia train/val/test theo nhóm. (ETL)
- [ ] Ghép `documents.json` và `qrels.json` theo [04](04_data_contract.md) mục 3. (ETL)
- [ ] Notebook EDA và biểu đồ. (ETL)

## Giai đoạn 3: Baseline

- [ ] Code đánh giá P/R/NDCG@K, có test. (Hung)
- [ ] TF-IDF, BM25 với cấu hình `C` và `C+Cm`. (?)
- [ ] Embedding có sẵn với cấu hình `C` và `C+Cm`. (?)

**→ Báo cáo tiến độ:** đủ dữ liệu sạch, EDA và kết quả baseline.

## Giai đoạn 4: Model chính và thí nghiệm

- [ ] Fine-tune bi-encoder, có thể thêm cross-encoder. (Hung)
- [ ] Chạy đủ các cấu hình và seed, ghi vào `experiments.csv`. (training)
- [ ] Phân tích lỗi, phân tích theo số lượng comment. (training)

## Giai đoạn 5: Nộp bài

- [ ] Báo cáo viết, đủ các mục ở [02](02_course_requirements.md). (báo cáo)
- [ ] Slide và demo 15 phút. (cả nhóm)
- [ ] `Readme.txt` và file zip source code. (ETL + model)
- [ ] Hoàn thiện bảng thư viện sử dụng ở [06](06_architecture.md#thư-viện-sử-dụng). (cả nhóm)
