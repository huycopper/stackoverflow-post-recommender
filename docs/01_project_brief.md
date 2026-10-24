# 01. Dự án này làm gì?

> **Tóm tắt.** Nhóm xây một hệ thống: đưa vào một câu hỏi lập trình trên Stack Overflow, hệ thống tìm ra những câu hỏi **đã có từ trước và hỏi cùng một vấn đề**. Mục tiêu chính là trả lời câu hỏi: *đọc thêm phần bình luận (comment) dưới câu hỏi có giúp tìm đúng hơn không?* Để biết hệ thống tìm đúng hay sai, nhóm dùng sẵn các cặp "câu hỏi trùng" mà cộng đồng Stack Overflow đã đánh dấu.

File này dành cho người chưa biết gì về dự án. Đọc xong bạn sẽ biết dự án giải bài toán gì, vì sao làm, đo kết quả thế nào và dữ liệu lấy từ đâu. Chi tiết kỹ thuật nằm ở các file khác trong `docs/`, có link ở cuối.

## 1. Bối cảnh: Stack Overflow và "câu hỏi trùng"

[Stack Overflow](https://stackoverflow.com) là trang hỏi đáp lập trình lớn nhất thế giới. Mỗi câu hỏi gồm:

- **Tiêu đề** và **nội dung** (thường có đoạn code bị lỗi).
- **Tag** cho biết chủ đề, ví dụ `python`, `pandas`.
- **Câu trả lời** của người khác.
- **Comment**: các bình luận ngắn ngay dưới câu hỏi hoặc câu trả lời. Ví dụ: người khác hỏi lại "bạn dùng Python phiên bản nào?", hoặc người hỏi bổ sung thông báo lỗi.

Rất nhiều câu hỏi mới thực ra **đã có người hỏi rồi**. Khi đó người kiểm duyệt **đóng câu hỏi mới là "duplicate" (trùng)** và gắn link tới câu hỏi cũ, gọi là **câu gốc**.

**Ví dụ thật:** câu hỏi số `79904105` bị đóng vì trùng với câu `38987` *"How do I merge two dictionaries in a single expression in Python?"* (gộp hai dictionary trong Python). Câu `38987` là một câu "kinh điển": có khoảng 450 câu hỏi khác liên kết tới nó.

Như vậy, mỗi lần có câu hỏi bị đóng vì trùng là một lần người hỏi không tự tìm được câu trả lời đã có sẵn. Một hệ thống gợi ý tốt sẽ giúp họ tìm ra ngay.

## 2. Hệ thống làm gì

| | Ví dụ |
|---|---|
| **Đầu vào** | Một câu hỏi: *"Combine two dicts into one without modifying the originals"*, kèm nội dung, tag và comment |
| **Đầu ra** | Danh sách **K** câu hỏi có sẵn trong kho, xếp từ liên quan nhất xuống (ví dụ K = 5) |
| **Đúng khi** | Câu gốc `38987` xuất hiện trong danh sách, càng gần đầu càng tốt |

Trong các docs khác, bài toán này được gọi là **xếp hạng (ranking)** hoặc **gợi ý top-K**. Câu hỏi đầu vào được gọi là **query**. Tập câu hỏi để tìm trong đó được gọi là **kho (corpus)**.

## 3. Câu hỏi chính dự án muốn trả lời

> **Thêm comment vào văn bản đưa cho model có giúp gợi ý đúng hơn so với chỉ dùng tiêu đề và nội dung không?**

Có lý do để nghĩ là có, và cũng có lý do để nghĩ là không:

- **Có thể giúp:** comment thường chứa thông tin mà nội dung còn thiếu, như thông báo lỗi đầy đủ, phiên bản thư viện, hay người hỏi giải thích lại mình thật sự muốn gì.
- **Có thể gây nhiễu:** nhiều comment chỉ là "thanks", "+1" hoặc lạc đề. Lại có nhiều câu hỏi không có comment nào.

Để trả lời, nhóm chạy **cùng một model** với hai loại văn bản đầu vào, rồi so sánh kết quả:

| Tên cấu hình | Văn bản đưa vào model |
|---|---|
| `C` (Content) | Tiêu đề + nội dung câu hỏi |
| `C+Cm` (Content + Comments) | Tiêu đề + nội dung + **comment** |

Nếu còn thời gian sẽ thử thêm `C+Cm+A`, tức thêm cả câu trả lời. Các model cụ thể (từ đơn giản như TF-IDF tới model ngôn ngữ) xem ở [07_modeling_eval.md](07_modeling_eval.md).

**Một bẫy cần tránh:** khi đóng câu hỏi trùng, Stack Overflow tự thêm comment kiểu *"Possible duplicate of …"* chứa luôn link tới câu gốc. Nếu giữ lại, model sẽ "nhìn thấy đáp án" và kết luận rằng comment giúp ích sẽ là kết luận sai. Vì vậy các comment này bị loại khi làm sạch dữ liệu ([05_cleaning_pipeline.md](05_cleaning_pipeline.md), bước 2).

## 4. Làm sao biết hệ thống gợi ý đúng?

Nhóm **không phải tự gán nhãn bằng tay**. Đáp án đúng lấy từ chính các đánh dấu "duplicate" của cộng đồng Stack Overflow:

- Lấy một câu hỏi đã bị đóng vì trùng làm query.
- Các câu hỏi **liên quan** với nó (đáp án đúng) là câu gốc của nó.
- Trùng có thể nối tiếp nhau. Nếu A trùng B và C cũng trùng B thì A, B, C hỏi cùng một vấn đề. Nhóm gom chúng thành một **nhóm trùng**, và mọi câu trong cùng nhóm đều tính là liên quan với nhau.

Khi chia dữ liệu để train và kiểm tra model, **cả nhóm trùng phải nằm cùng một phía**. Nếu không, model sẽ được "học trước" đúng cặp mà sau đó bị kiểm tra.

## 5. Đo chất lượng bằng chỉ số nào?

Ba chỉ số, đều tính trên **K kết quả đầu tiên** (dự kiến K = 5 và K = 10):

| Chỉ số | Ý nghĩa dễ hiểu |
|---|---|
| **Precision@K** | Trong K câu gợi ý, bao nhiêu phần là đúng? |
| **Recall@K** | Trong tất cả các câu đúng, tìm ra được bao nhiêu phần trong K câu đầu? |
| **NDCG@K** | Giống Recall nhưng có tính thứ tự: câu đúng đứng càng cao thì điểm càng cao |

**Ví dụ:** query có 2 câu liên quan. Hệ thống gợi ý 5 câu, trong đó 1 câu đúng ở vị trí thứ 3.

- Precision@5 = 1/5 = 0,2
- Recall@5 = 1/2 = 0,5
- NDCG@5 ≈ 0,31. Nếu câu đúng đó đứng ở vị trí 1 thì NDCG@5 ≈ 0,61.

Điểm cuối cùng là trung bình trên tất cả các query trong tập kiểm tra. Cấu hình `C+Cm` được coi là tốt hơn `C` nếu các chỉ số này cao hơn một cách rõ ràng.

## 6. Dữ liệu lấy từ đâu?

- Lấy qua **API chính thức của Stack Exchange** (công ty sở hữu Stack Overflow), bắt đầu với tag `python`.
- Không scrape trực tiếp trang web, vì trang web chặn bot bằng Cloudflare và nhóm quyết định không tìm cách lách.
- Dữ liệu API trả về vẫn rất "bẩn": nội dung là HTML có lẫn code, ngày tháng ở dạng số, có comment làm lộ đáp án… Vì vậy dự án có một bước **làm sạch dữ liệu** riêng. Bước này bắt buộc theo yêu cầu của môn học.
- Quy mô dự kiến: vài chục nghìn câu hỏi, kèm câu trả lời và comment.

Chi tiết: [03_data_source.md](03_data_source.md) (cách lấy), [04_data_contract.md](04_data_contract.md) (định dạng sau khi làm sạch).

## 7. Toàn bộ quy trình

```
1. Thu thập        Gọi API, lưu dữ liệu thô
2. Làm sạch        Bóc HTML, lọc comment lộ đáp án, ghép bảng, gom nhóm trùng
3. EDA             Thống kê, vẽ biểu đồ để hiểu dữ liệu
4. Mô hình         Chạy các model với cấu hình C và C+Cm
5. Đánh giá        Tính Precision / Recall / NDCG @K, so sánh
6. Báo cáo         Báo cáo viết, slide, demo 15 phút
```

Bước 1–3 do nhóm ETL làm, bước 4–6 do nhóm model và training làm. Ai làm gì xem [08_team_workflow.md](08_team_workflow.md), tiến độ xem [09_roadmap.md](09_roadmap.md).

## 8. Phạm vi

**Có làm:**

- Chỉ Stack Overflow, bắt đầu với tag `python` (có thể thêm tag khác, chưa chốt).
- Chỉ câu hỏi tiếng Anh.
- Một demo đơn giản: nhập câu hỏi, ra danh sách gợi ý.

**Không làm:** hệ thống chạy thời gian thực, giao diện người dùng hoàn chỉnh, các trang Stack Exchange khác ngoài Stack Overflow.

## 9. Kết quả này dùng vào đâu?

- Gợi ý "câu hỏi liên quan" khi người dùng đang đọc một câu hỏi.
- Cảnh báo "câu này có thể đã được hỏi rồi" ngay khi người dùng đang gõ câu hỏi mới. Như vậy giảm câu hỏi lặp và đỡ việc cho người kiểm duyệt.
- Kết luận về vai trò của comment có thể áp dụng cho các diễn đàn hỏi đáp và cộng đồng khác.

## 10. Đề tài đã đăng ký với môn học

Nhóm đã nộp qua form *Project Registration DS* ngày 14/10/2026, với tên đề tài **Content- and Comment-Based Post Recommendation**:

> We build a top-K post recommender that uses both post content and comments. The learning problem is a ranking task with input as a query post, and output as K most relevant posts. Our objective is to test whether adding comment information improves recommendation quality over using post content alone. Data is scraped from social media platforms via web scraping, then cleaned and converted into a standardized format. Posts and comments are represented as text features, and relevance is judged using topic labels and user interaction signals. We evaluate with Precision@K, Recall@K, and NDCG@K.

Từ lúc đăng ký đến nay, kế hoạch đã đổi hai điểm (**cần báo TA**, xem [decisions.md](decisions.md)):

| | Khi đăng ký | Hiện tại |
|---|---|---|
| Nguồn dữ liệu | Mạng xã hội, scrape trang web | Stack Overflow, qua API chính thức |
| Cách xác định "liên quan" | Nhãn chủ đề và tương tác người dùng | Đánh dấu câu hỏi trùng của Stack Overflow |

## Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| Query | Câu hỏi đầu vào, cần tìm câu liên quan cho nó |
| Kho (corpus) | Toàn bộ câu hỏi mà hệ thống tìm trong đó |
| Câu gốc (original) | Câu hỏi cũ mà câu trùng trỏ tới |
| Nhóm trùng | Các câu hỏi cùng hỏi một vấn đề, nối với nhau bằng quan hệ trùng |
| Top-K | K kết quả đầu tiên của danh sách gợi ý |
| `C`, `C+Cm` | Hai cấu hình văn bản đầu vào: chỉ nội dung, và nội dung + comment |
| ETL | Extract – Transform – Load: thu thập, làm sạch và lưu dữ liệu |
| EDA | Exploratory Data Analysis: phân tích khám phá dữ liệu bằng thống kê và biểu đồ |

## Đọc tiếp

- Yêu cầu và tiêu chí chấm của môn: [02_course_requirements.md](02_course_requirements.md)
- Vì sao chọn hướng này: [decisions.md](decisions.md)
- Đang làm tới đâu: [09_roadmap.md](09_roadmap.md)
