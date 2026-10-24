# 07. Model và đánh giá

> **Trạng thái: đề xuất.** Bên model (Hung) sẽ chốt. Trong nhóm đã thống nhất "phần model sẽ bàn kĩ sau" (16/10/2026).

## Giao thức đánh giá

- **Query:** các câu hỏi bị đóng vì trùng nằm trong tập `test`.
- **Kho tìm kiếm (corpus):** tất cả câu hỏi trong tập `test` và câu hỏi nền. Bỏ chính câu query ra khỏi kết quả.
- **Câu liên quan:** các câu khác cùng `group_id` với query ([04](04_data_contract.md)).
- **Chỉ số:** Precision@K, Recall@K, NDCG@K, với K ∈ {5, 10}. Có thể báo thêm MRR.
- **Chia dữ liệu theo nhóm trùng** để model không học thuộc đúng cặp trùng sẽ bị kiểm tra.
- Giữ cố định seed. Báo cáo kết quả trung bình và độ lệch nếu chạy nhiều seed.

## Thí nghiệm chính: ablation theo văn bản đầu vào

| Cấu hình | Văn bản |
|---|---|
| `C` | `title` + `body` |
| `C+Cm` | `title` + `body` + `comments` |
| `C+Cm+A` (tùy chọn) | thêm `answers` |

Các trường lấy từ `documents.json` ([04](04_data_contract.md#3-dữ-liệu-đưa-vào-model-datacleandocumentsjson)), nhãn đúng lấy từ `qrels.json`.

Mỗi cấu hình chạy với **cùng model và cùng tham số**. Chỉ thay văn bản đầu vào để so sánh công bằng.

Phân tích thêm: chỉ xét các query **có comment** (vì nhiều câu hỏi không có comment nào), và chia kết quả theo số lượng comment.

## Các model đề xuất (từ đơn giản đến phức tạp)

1. **Baseline từ vựng:** TF-IDF + cosine, BM25.
2. **Embedding có sẵn, không train:** Sentence-BERT (ví dụ `all-MiniLM-L6-v2`) hoặc `bge-small`, sau đó tìm kiếm theo cosine.
3. **Fine-tune bi-encoder** trên cặp trùng của tập `train` (contrastive, in-batch negatives). Đây là phần "học máy" mà mô tả đề tài yêu cầu.
4. *(Tùy chọn)* **Cross-encoder xếp hạng lại** top-N từ bước 2 hoặc 3.

Model mạnh nhất cũng phải so với baseline 1 và 2.

## Ghi kết quả thí nghiệm

- Mỗi lần chạy thêm một dòng vào `results/experiments.csv`, gồm: ngày, người chạy, model, cấu hình văn bản, tham số chính, seed, các chỉ số @K, commit hash.
- Config của mỗi lần chạy lưu trong `config/experiments/*.toml` để chạy lại được.
- Checkpoint model **không commit**, lưu ở Drive hoặc ổ của nhóm và ghi đường dẫn vào cột ghi chú.

## Câu hỏi mở

- [ ] Có fine-tune không, hay chỉ so sánh các model có sẵn? (Phụ thuộc GPU và thời gian, Colab có thể đủ.)
- [ ] Chọn những giá trị K nào?
- [ ] Ghép comment kiểu gì: nối chuỗi, hay encode riêng rồi gộp embedding?
