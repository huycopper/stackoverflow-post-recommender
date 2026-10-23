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
- [x] Lấy mẫu kèm câu trả lời, comment và quan hệ trùng: 1.210 câu hỏi, 308 cặp trùng, 4.120 câu trả lời, 14.540 comment, tốn 218 request (`config/collect_sample.toml`, 24/10). (Huy Copper)
- [ ] Gửi mẫu cho bên model, chốt data contract lên **1.0**. (ETL + Hung)
- [ ] Lấy dữ liệu đầy đủ theo chiến lược lấy mẫu ở [03](03_data_source.md). (ETL)

## Giai đoạn 2: Làm sạch, tích hợp, EDA

- [ ] 6 bước làm sạch và `cleaning_stats.json`. (Nguyễn Huy)
- [ ] Nhóm trùng và chia train/val/test theo nhóm. (ETL)
- [ ] Ghép `documents.parquet`. (ETL)
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
