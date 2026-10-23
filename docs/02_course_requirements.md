# 02. Yêu cầu của môn học

Nguồn: slide `L0-course-inf-en` (slide 6–9) và các câu trả lời của TA. Đây là checklist để **đối chiếu trước khi nộp**.

## Hình thức chấm

- Capstone project là bài giữa kỳ, chiếm **40%** điểm. Thi cuối kỳ trắc nghiệm chiếm 60%.
- Nhóm 4–6 người. Mỗi nhóm chọn một bài toán phân tích dữ liệu, đề xuất giải pháp, cài đặt và đánh giá hiệu quả.
- Mỗi thành viên đều phải đóng góp vào project và phần thuyết trình.

## Tiêu chí chấm (slide 9)

| Tiêu chí | Cách dự án đáp ứng |
|---|---|
| Độ khó của bài toán | Bài toán xếp hạng, có thu thập, làm sạch, tích hợp dữ liệu và thí nghiệm so sánh |
| Phương pháp phù hợp và có chất lượng | Có baseline và model mạnh hơn, xem [07](07_modeling_eval.md) |
| Đánh giá thực nghiệm chặt chẽ | P/R/NDCG@K, chia dữ liệu theo nhóm trùng, ablation `C` so với `C+Cm` |
| Chất lượng thuyết trình | 15 phút gồm slide và **demo** |
| Chất lượng báo cáo viết | Xem mục "Sản phẩm nộp" bên dưới |
| Khai báo thư viện, code có sẵn | **Bắt buộc** ghi trong báo cáo và slide. Danh sách nằm ở [06](06_architecture.md#thư-viện-sử-dụng) |

## Sản phẩm nộp (slide 8)

- **Source code:** một file zip.
- **Readme.txt:** mô tả rõ cách cài đặt, biên dịch và chạy.
- **Báo cáo viết**, gồm:
  - [ ] Giới thiệu bài toán và các bộ dữ liệu đã dùng
  - [ ] Chi tiết các phương pháp phân tích dữ liệu
  - [ ] Kết quả các đánh giá, kết luận và phát hiện mới
  - [ ] Các thành phần chính của code
  - [ ] **Khó khăn gặp phải và giải pháp**. Ví dụ: Cloudflare chặn scrape, dữ liệu HTML bẩn, comment làm lộ đáp án

## Đề xuất đề tài (slide 7)

Cần có: mô tả ngắn, input, output, kiểu dữ liệu, ứng dụng, thuật toán và công cụ, nguồn dữ liệu sẽ crawl. Hạn đăng ký là **14/10/2026** (nhóm đã nộp). Nội dung đã đăng ký xem [01_project_brief.md](01_project_brief.md).

## Câu trả lời của TA (Tran Vu Manh Duc, 16/10/2026)

1. **Vấn đề pháp lý không phải tiêu chí chấm.** Nhiều nhóm vẫn dùng dữ liệu có bản quyền.
2. **Cách thu thập không quan trọng.** Scrape, gọi API hay dùng agent đều được tính là bước thu thập dữ liệu. Nhưng nếu chỉ có một người gọi API thì phần việc đó quá mỏng. Điều quan trọng là cách lấy và làm sạch dữ liệu.
3. **Bắt buộc có bước thu thập và làm sạch thật sự.** Nếu dữ liệu thu về đã sạch sẵn và không có bước này, nhóm **bị trừ khoảng 20% điểm**.
4. Khi thuyết trình phải **nêu rõ khó khăn** gặp phải với dữ liệu thu thập được.

TA **chưa trả lời** câu hỏi "Stack Overflow có được tính là nền tảng mạng xã hội không" (đề tài đăng ký ghi *social media platforms*). Đây là câu hỏi mở, xem [decisions.md](decisions.md).

## Các bài giảng liên quan

| Phần của dự án | Bài giảng |
|---|---|
| Thu thập dữ liệu, robots.txt, đạo đức khi crawl | L2 Web crawling |
| Làm sạch và tích hợp dữ liệu | L3 Data integration & preprocessing |
| EDA | L4 Exploratory analysis |
| Trực quan hóa | L5–6 DataViz |
| Model | L7 Machine learning |
| Lưu trữ dữ liệu lớn (nếu dùng) | L8 Big data management |
| Xử lý văn bản, đồ thị liên kết | L10–11 Text / Link analysis |
| Đánh giá | L12 Evaluation |

## Mốc thời gian

| Mốc | Ngày |
|---|---|
| Đăng ký đề tài | 14/10/2026 (đã nộp) |
| Báo cáo tiến độ | Chưa có ngày (slide ghi "1 week") |
| Báo cáo cuối và thuyết trình | Chưa có ngày (slide ghi "3–4 weeks" cuối kỳ) |

Có ngày chính thức thì cập nhật bảng này và [09_roadmap.md](09_roadmap.md).
