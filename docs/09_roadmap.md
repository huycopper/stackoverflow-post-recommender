# 09. Kế hoạch

Cập nhật lần cuối: **16/11/2026**. Ngày báo cáo tiến độ và báo cáo cuối **chưa có**. Khi có thì thêm vào đây và vào [02](02_course_requirements.md#mốc-thời-gian).

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
  - Đã dừng thu thập và tắt lịch 22:00 ngày 26/10 (D11). Muốn lấy thêm thì tăng `seed_pages_per_tag` hoặc thêm tag, rồi bật lại lịch.
- [x] Thu thập thêm tới 200 trang seed (D14): chạy từ 14:46 tới 16:42 ngày 29/10, xong trong một lần chạy (6.524 request, còn dư 3.420 quota). Dữ liệu 532 MB trong `data/raw/`, tóm tắt ở `data/exports/full_summary_20261029.json`. Đã tắt lại lịch 22:00. (Huy Copper)
  - **151.919 câu hỏi** (thêm 58.215): 20.000 seed, 100 background, còn lại là câu liên kết và câu gốc. 29.941 câu bị đóng vì trùng, ra **34.653 cặp trùng** (thêm 11.183). Thiếu 4 câu gốc vì đã bị xóa.
  - 384.330 câu trả lời: thiếu 2 câu so với `answer_count`, ở 3 câu hỏi.
  - Comment: 571.918 comment của câu trả lời (đủ). 405.115 trên 409.497 comment của câu hỏi, vì có 1.118 câu API không trả comment. 22.593 comment làm lộ đáp án, cần lọc.
  - 74,5% câu hỏi có comment. Trong các câu trùng, 22.852 trên 29.941 câu (76%) có comment.
  - 57 batch `linked` chạm giới hạn 3 trang.
- [ ] Gửi bản raw mới `data/exports/so_raw_jsonl_20261029_v2.zip` (557 MB, 200 trang seed, đã kiểm tra không chứa API key) cho Nguyễn Huy qua Drive (D15). Bản này chứa cả dữ liệu của bản gửi lúc 14:30. (Huy Copper)
- [x] Sửa lỗi phân trang của bước `linked`: lật theo cửa sổ ngày tạo (`todate`) thay cho `page` (14/11, D16). (Huy Copper)
- [x] Chạy `repair` rồi `run` để lấy lại câu `linked` của 8.760 seed bị cắt ở 100 câu. Ước tính khoảng 20 nghìn request, tức khoảng 2 ngày quota (D16). Thực tế tốn khoảng 12.250 request trong 2 tối (14–15/11). (Huy Copper)
  - 14/11: đã chạy `repair` (8.760 seed vào lại hàng đợi), sao lưu state cũ ở `data/collect_state.backup_20261114_before_d16.json`. Lần `run` đầu tiên bắt đầu lúc 22:06, log ở `data/logs/collect_20261114_d16.log`.
  - Đã bật lại lịch 22:00 để mỗi tối tự chạy tiếp, lần đầu vào 22:00 ngày 15/11. `seed_pages_per_tag` vẫn là 200, nên lịch chỉ lấy nốt phần lấy lại này, chưa thêm seed mới.
  - 15/11: lần chạy đầu dừng lúc 00:32 vì Windows khóa file state (33 MB). Đã sửa (`abb390e`) và chạy tiếp từ 00:33 tới 01:42 thì hết quota, log ở `data/logs/collect_20261115_d16b.log`. Cả đêm tốn khoảng 9.900 request.
  - Phần `linked` của cả 8.760 seed đã xong, không batch nào chạm giới hạn 50 cửa sổ. Hiện có **275.903 câu hỏi** (thêm 123.984) và **69.773 cặp trùng** (thêm 35.120, nhiều hơn mức ước tính 20 nghìn). Câu gốc, câu trả lời và comment của câu hỏi đã đủ.
  - Lịch 22:00 ngày 15/11 chạy nốt comment của câu trả lời và tag synonyms, xong lúc 22:41 (2.348 request, còn dư 7.652 quota). Log ở `data/logs/collect_20261115_2200.log`, tóm tắt ở `data/exports/full_summary_20261116.json`, dữ liệu 839 MB trong `data/raw/`.
  - Kết quả cuối: **275.903 câu hỏi**, trong đó 62.135 câu bị đóng vì trùng, ra **69.773 cặp trùng**. Thiếu 12 câu gốc vì đã bị xóa.
  - 587.291 câu trả lời: thiếu 9 câu so với `answer_count`, ở 17 câu hỏi.
  - Comment: 836.766 comment của câu trả lời (đủ). 747.680 trên 752.317 comment của câu hỏi, vì có 1.184 câu API không trả comment. 41.855 comment làm lộ đáp án, cần lọc.
  - 76,4% câu hỏi có comment. Trong các câu trùng, 48.317 trên 62.135 câu (78%) có comment.
  - Lịch 22:00 vẫn bật, nhưng với 200 trang seed thì không còn gì để lấy.
- [x] Sau đó tăng `seed_pages_per_tag` lên quá 200 (D16): tăng lên 300 ngày 16/11. (Huy Copper)
- [ ] Thu thập tới 300 trang seed: lịch 22:00 bắt đầu lấy từ tối 16/11, tiếp từ trang 201. Ước đoán (chưa đo) tốn dưới một ngày quota, vì seed sắp theo vote nên các trang sau ít câu liên kết hơn. (Huy Copper)
- [ ] Báo cả nhóm về D16, vì nó thay thỏa thuận "chưa crawl lại" ngày 31/10. (Huy Copper)
- [x] Xuất dữ liệu để khám phá: `data/flat/*.parquet` và `data/exports/explore_20261026.xlsx` (26/10). (Huy Copper)
- [x] Gửi dữ liệu cho Nguyễn Huy qua Drive. (Huy Copper)
  - 26/10: `data/flat/` (4 bảng Parquet) và file Excel.
  - 29/10: bản raw `.jsonl.gz` có cả `tag_synonyms` (`data/exports/so_raw_jsonl_20261029.zip`). Từ đây giao raw thay cho bản phẳng (D15).
- [ ] Xem dữ liệu, tìm insight, chốt các bước làm sạch. (Nguyễn Huy, nhận việc từ 26/10, D12)

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
