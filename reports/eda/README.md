# EDA: dữ liệu Stack Overflow sau khi làm sạch

Phân tích khám phá trên các bảng trong `data/clean/` (kết quả của pipeline Spark). Bố cục bám theo bài giảng **L4 Exploratory data analysis**: xét từng biến một (thống kê tóm tắt, histogram, box plot, bar chart, run sequence), sau đó xét quan hệ giữa các biến (scatter plot, scatterplot matrix, tương quan), cuối cùng là tìm cấu trúc trong dữ liệu (cosine similarity, SVD, k-means).

Chạy lại (khoảng 30 giây):

```bash
uv run --group eda python -m so_recommender.eda
```

Số liệu đầy đủ nằm trong `summary.json`, hình nằm trong `figures/`. Mọi con số dưới đây lấy từ lần chạy ngày 31/10/2026.

## 1. Dữ liệu và kiểu biến

| Bảng | Số dòng |
|---|---:|
| Câu hỏi | 93.704 |
| Câu trả lời | 257.960 |
| Comment | 632.388 (240.116 dưới câu hỏi, còn lại dưới câu trả lời) |
| Cặp trùng | 23.467 |
| Nhóm trùng | 4.806 |

Câu hỏi được đăng từ 02/08/2008 đến 24/10/2026.

| Biến | Kiểu |
|---|---|
| `title`, `body_text`, `body_code`, comment | Văn bản |
| `tags` | Phân loại, nhiều giá trị trên một câu |
| `closed_reason`, `split`, `is_closed_duplicate` | Phân loại |
| `score`, `view_count`, `answer_count`, `comment_count` | Số, rời rạc (`score` có thể âm) |
| `creation_date` | Thời gian |
| Vai trò: câu trùng / câu gốc / câu khác | Phân loại, suy ra từ `duplicate_pairs` |

**Vai trò** của một câu hỏi:
- **Câu trùng (query):** câu bị đóng vì trùng. Có 20.101 câu.
- **Câu gốc:** câu mà câu trùng trỏ tới. Có 7.182 câu.
- **Câu khác:** còn lại. Có 66.421 câu.

## 2. Từng biến một

### Thống kê tóm tắt của câu hỏi

| Biến | Mean | Median | Mode | Std | Skewness | Kurtosis |
|---|---:|---:|---:|---:|---:|---:|
| `score` | 34,5 | 1 | 0 | 203,6 | 42,3 | 4.106 |
| `view_count` | 48.760 | 1.026 | 1 | 219.245 | 13,7 | 301 |
| `answer_count` | 2,75 | 1 | 1 | 4,22 | 5,9 | 85 |
| `comment_count` | 2,56 | 2 | 0 | 2,89 | 2,2 | 8,9 |
| Độ dài tiêu đề (ký tự) | 57,3 | 54 | 45 | 21,8 | 1,06 | 1,6 |
| Độ dài body (từ, không tính code) | 93,6 | 75 | 57 | 74,4 | 3,8 | 35,6 |
| Số khối code | 1,70 | 1 | 1 | 1,46 | 1,9 | 11,9 |
| Số tag | 3,03 | 3 | 3 | 1,19 | 0,10 | −0,87 |

Thêm: câu trả lời có trung vị 41 từ, và mode bằng 0 vì có những câu trả lời chỉ gồm code. Comment có trung vị 22 từ. 19,7% câu trả lời được chấp nhận.

**Nhận xét:**
- `score` và `view_count` **lệch phải rất mạnh** (skewness 42 và 14). Mean gấp hàng chục lần median, vì có vài câu kinh điển với hàng triệu lượt xem. Theo slide L4, với phân phối lệch như vậy thì **nên dùng median, không dùng mean**, và nên vẽ trên thang log.
- Độ dài tiêu đề và số tag gần đối xứng. Riêng số tag có kurtosis âm vì bị chặn ở 1–5 tag.
- Số comment có mode bằng 0: 25.246 câu hỏi (26,9%) không có comment nào (hình 3).

### Hình

- **Hình 1** `fig01_questions_per_month.png` (run sequence plot). Số câu hỏi tăng đều tới đỉnh năm 2020–2021 (khoảng 1.200 câu/tháng), sau đó giảm mạnh từ năm 2023. Đường câu trùng đi theo cùng dạng. Dữ liệu vì vậy nghiêng về giai đoạn 2018–2022.
- **Hình 2** `fig02_top_tags.png`. `python` có mặt ở 81.646 câu hỏi. Tiếp theo là `python-3.x` (13.130), `pandas` (12.490), `dataframe` (4.809), `django` (4.645), `matplotlib` (4.164), `numpy` (4.163). Sau khi đổi tag đồng nghĩa còn 8.503 tag khác nhau.
- **Hình 3** `fig03_histograms.png`. Độ dài body và độ dài comment có dạng gần chuông **trên thang log** (phân phối gần log-normal). Số comment trên mỗi câu hỏi giảm dần đều từ 0.

### Theo vai trò (box plot, hình 4 `fig04_boxplots_by_role.png`)

| | Câu trùng | Câu gốc | Câu khác |
|---|---:|---:|---:|
| Không có comment | 24,8% | 35,0% | 26,7% |
| Không có câu trả lời | 25,5% | 0% | 10,7% |
| Có khối code | 84,5% | 75,8% | 82,0% |
| Trung vị số comment | 2 | 1 | 2 |
| Trung vị độ dài body (từ) | 62 | 61 | 81 |

**Nhận xét:**
- **Khoảng 1/4 câu trùng không có comment.** Với những câu này, cấu hình `C+Cm` không khác gì `C`. Khi đánh giá nên tách riêng nhóm câu có comment, như `docs/07` đã đề xuất.
- Câu trùng ngắn hơn câu thường (62 so với 81 từ) và một phần tư không có câu trả lời, vì chúng bị đóng trước khi ai kịp trả lời.
- Câu gốc có điểm cao hơn hẳn (hình 4, cột phải). Đây là các câu kinh điển.

## 3. Quan hệ giữa các biến

- **Hình 5** `fig05_score_vs_views.png` (scatter, 20.000 câu ngẫu nhiên). Điểm và lượt xem tăng cùng nhau gần tuyến tính trên thang log-log. Câu gốc (xanh) tập trung ở góc nhiều lượt xem, điểm cao. Câu trùng (cam) nằm ở vùng ít lượt xem, điểm quanh 0.
- **Hình 6** `fig06_scatter_matrix.png` (scatterplot matrix, 3.000 câu, thang log1p).
- **Hình 7** `fig07_correlation.png` (tương quan Spearman):
  - Ba biến `score`, `view_count`, `answer_count` tương quan mạnh với nhau (ρ = 0,75; 0,66; 0,56).
  - `comment_count` gần như **không tương quan** với biến nào (|ρ| ≤ 0,09). Số comment không phải là thước đo độ nổi tiếng mà là một tín hiệu riêng, nên đáng thử trong cấu hình `C+Cm`.

## 4. Nhóm trùng

**Hình 8** `fig08_group_sizes.png`. Phân phối kích thước nhóm lệch rất mạnh:

| Kích thước | 2 | 3 | 4–5 | 6–10 | 11–50 | 51–200 | > 200 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Số nhóm | 2.624 | 833 | 657 | 463 | 210 | 18 | 1 |

- **Một nhóm duy nhất chứa 8.042 câu hỏi.** Nhóm lớn tiếp theo chỉ có 162 câu. Pipeline đưa cả nhóm này vào tập train, để tập test không bị một chủ đề chiếm phần lớn.
- Mỗi câu trùng trỏ tới trung bình 1,17 câu gốc. 99% trỏ tới tối đa 3 câu, tối đa là 5.

## 5. Độ giống nhau về từ vựng: thêm comment có giúp không?

Mỗi câu hỏi được biểu diễn bằng vector TF-IDF. Văn bản lấy theo hai cấu hình: `C` là tiêu đề cộng body; `C+Cm` thêm comment của câu hỏi. Em đo cosine similarity của 23.467 cặp trùng và của cùng số cặp ngẫu nhiên (không cùng nhóm). Kết quả ở **hình 9** `fig09_similarity.png`.

| | C: cặp trùng | C: cặp ngẫu nhiên | C+Cm: cặp trùng | C+Cm: cặp ngẫu nhiên |
|---|---:|---:|---:|---:|
| Trung vị | 0,152 | 0,012 | 0,159 | 0,018 |
| Phân vị 10% | 0,032 | 0 | 0,053 | 0 |
| Phân vị 90% | 0,350 | 0,050 | 0,315 | 0,054 |
| Tỉ lệ cặp trùng vượt phân vị 95% của cặp ngẫu nhiên | 78,8% | | **85,2%** | |

**Nhận xét:**
- Cặp trùng giống nhau hơn cặp ngẫu nhiên rất rõ (trung vị 0,15 so với 0,01). Nhãn từ quan hệ trùng vì vậy có ý nghĩa về mặt nội dung.
- Thêm comment **không làm cặp trùng giống nhau hơn về trung bình**: 47% cặp tăng, 52% cặp giảm, trung bình thay đổi gần 0. Nhưng phân phối **co lại**:
  - Các cặp khó (phân vị 10%) tăng từ 0,032 lên 0,053.
  - Các cặp dễ (phân vị 90%) giảm từ 0,350 xuống 0,315.
  - Kết quả là cặp trùng **tách khỏi cặp ngẫu nhiên tốt hơn**: 85,2% so với 78,8%.
- Đây là **tín hiệu ban đầu** rằng comment có thể giúp ở những câu mà nội dung thôi không đủ. Cần thận trọng: đây chỉ là TF-IDF đơn từ và là phép đo theo cặp, chưa phải chỉ số xếp hạng Precision/Recall/NDCG@K. Kết luận chính thức phải đợi phần mô hình.

## 6. Cấu trúc trong văn bản (SVD và k-means)

- **Hình 10** `fig10_svd_by_tag.png`. TF-IDF của 20.000 câu hỏi ngẫu nhiên, chiếu xuống 2 chiều bằng SVD. Câu `pandas` (xanh) tách lên phía trên, câu `django` (cam) nằm phía dưới, còn `numpy` (xanh lá) chồng lên vùng `pandas`. Chủ đề thư viện là trục khác biệt lớn nhất trong văn bản.
- **Hình 11** `fig11_kmeans_elbow.png`. Inertia của k-means giảm đều từ k = 2 đến 12, **không có khuỷu rõ**. Văn bản không tách thành vài cụm gọn. Em chọn k = 8 để mô tả:

| Cụm | Số câu | Từ đặc trưng | Chủ đề |
|---:|---:|---|---|
| 2 | 6.767 | code, function, class, use | Câu hỏi Python chung |
| 0 | 3.028 | file, script, py, run, error | Chạy script, file |
| 6 | 2.414 | django, flask, request, html, app | Web |
| 5 | 2.311 | dataframe, column, pandas, rows | pandas |
| 1 | 1.816 | list, elements, values | List |
| 3 | 1.507 | install, pip, version, package | Cài đặt |
| 4 | 1.259 | string, convert, characters | Chuỗi |
| 7 | 898 | plot, matplotlib, axis, graph | Vẽ đồ thị |

## 7. Hệ quả cho các bước tiếp theo

1. **Dùng median và thang log** cho `score`, `view_count`, độ dài. Không dùng mean để mô tả các biến này.
2. **Báo cáo kết quả riêng cho câu có comment.** Khoảng 25% câu trùng không có comment.
3. **Nhóm 8.042 câu cần được bàn riêng** với người làm mô hình. Hiện cả nhóm nằm trong train, và `qrels.json` chỉ lấy câu gốc trực tiếp làm đáp án cho các query của nhóm này.
4. **Comment giúp ở các cặp khó** theo phép đo TF-IDF. Phần mô hình nên phân tích kết quả theo độ khó của cặp (độ giống ban đầu thấp hay cao), không chỉ xem trung bình.
5. **Văn bản chia theo chủ đề thư viện** (pandas, Django, matplotlib…). Có thể dùng tag làm đặc trưng phụ, hoặc làm bộ lọc ứng viên khi xếp hạng.
