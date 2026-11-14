# 05. Làm sạch và tích hợp dữ liệu

Bước này chiếm khoảng **20% điểm**. Nếu dữ liệu sạch sẵn mà không có bước làm sạch, nhóm bị trừ ([02](02_course_requirements.md)). Vì vậy mỗi bước đều phải **có lý do, có số liệu và có ví dụ trước/sau** để đưa vào báo cáo.

Input: `data/raw/`. Output: các bảng trong [04_data_contract.md](04_data_contract.md). Bước này không tạo cặp trùng, không gom nhóm trùng và không chia train/val/test ([decisions.md](decisions.md), D13).

## Ví dụ dữ liệu thô từ API

Body câu hỏi:

```html
<p>I'm trying to merge two dictionaries ... there's a concise way ...</p>
<pre class="lang-py prettyprint-override"><code>dict1 = {'a': 1, 'b': 2}
</code></pre>
```

Câu trả lời có `<h2>`, `<a href=...>` và khối code xen giữa chữ. Ngày ở dạng số Unix (ví dụ `1773085962`). Có những câu hỏi trùng không có comment nào.

## Các bước

### 1. Bóc HTML và tách code khỏi chữ

- Code khối (`<pre><code>`) tách sang `body_code`. Code chèn trong câu (`<code>`) thì giữ lại dưới dạng chữ.
- Bỏ thẻ HTML, giải mã ký tự HTML (`&#39;` thành `'`, `&quot;` thành `"`…), chuẩn hóa dấu nháy và khoảng trắng.
- **Số liệu:** độ dài trung bình trước và sau, tỉ lệ bài có code.

### 2. Lọc comment làm lộ đáp án

- Loại các comment tự sinh hoặc trỏ thẳng tới câu trùng, ví dụ "Possible duplicate of …", "Does this answer your question? …", "This question already has an answer here".
- Mẫu được so trên nội dung comment đã bỏ thẻ HTML, để bắt cả "Does <a…>this</a> answer your question?".
- **Link tới câu hỏi hoặc câu trả lời khác trên Stack Overflow và các trang Stack Exchange khác (meta.stackoverflow.com, superuser.com, *.stackexchange.com...) được thay bằng `[link]`**, ở comment, body câu hỏi và body câu trả lời. Ví dụ "Also, related: Convert pandas dataframe to NumPy array" (chữ của link là tiêu đề câu gốc) thành "Also, related: [link]". Dòng bị thay có cờ `SO_LINK_REPLACED` ở trường `text` (comment) hoặc `body_text` (câu hỏi, câu trả lời).
  - Comment: thay hai lượt, trên HTML gốc (thẻ `<a>`, URL trần) rồi trên văn bản đã bóc HTML, để bắt URL bị thẻ hoặc ký tự vô hình chia đôi.
  - Body: thay thẻ `<a>` trên HTML gốc và URL trần trên phần chữ. **Code trong khối `<pre>` giữ nguyên**, vì code có thể chứa URL thật cần thiết.
  - Link ra ngoài (tài liệu Python, github, trang `/help/...`) giữ nguyên, vì thường có từ khóa hữu ích và không trỏ tới câu hỏi nào.
- Xóa khung "Possible Duplicate: [link]" mà Stack Overflow tự chèn ở đầu body câu hỏi bị đóng vì trùng (trước khoảng 2013). Chỉ xóa khung ở đầu body; câu người hỏi tự viết về câu trùng thì giữ. Cờ `DUPLICATE_BANNER_REMOVED` ở `body_text`.
- Comment chỉ có link sang câu hỏi khác (sau khi thay chỉ còn `[link]`, dấu câu, ký hiệu và khoảng trắng) bị **loại** ở bước chuẩn hóa với lý do `ONLY_LINK`, giống comment rỗng.
- Bỏ cặp ký tự vô hình (U+200C U+200B) mà Stack Overflow chèn vào giữa từ dài trong comment để xuống dòng; có ở 4.881 comment. Body câu hỏi và câu trả lời giữ nguyên, vì vài câu có thể đang hỏi chính về ký tự vô hình.
- **Lý do:** nếu giữ lại, model `C+Cm` sẽ "nhìn thấy đáp án" và kết luận về vai trò của comment sẽ sai. Đo ngày 12/11/2026: 50.910 comment (8,1%) có link kiểu này, trong đó 2.520 comment dưới 2.306 câu trùng trỏ thẳng tới câu gốc của nó. Ví dụ thật: `data/exports/comment_links_review_20261112.xlsx`.
- **Số liệu:** số comment bị loại theo từng mẫu.

### 3. Ghép dữ liệu từ nhiều endpoint (data integration, bài L3)

- Câu hỏi, câu trả lời và comment đến từ các endpoint khác nhau, phải nối lại theo ID.
- Các trường hợp lệch cần xử lý:
  - Comment không tìm thấy bài cha.
  - Một bài xuất hiện ở nhiều tag hoặc nhiều trang nên bị trùng bản ghi: khử trùng theo ID và giữ bản lấy mới nhất.
- **Số liệu:** số bản ghi trùng đã khử, số bản ghi mồ côi.

### 4. Lọc bài kém chất lượng

Code ở `clean/steps/quality.py`, ngưỡng ở mục `[quality]` và `[low_info_comments]` của `config/clean.toml`. Lý do chọn từng ngưỡng ghi ở [decisions.md](decisions.md), D14. Ví dụ thật quanh từng ngưỡng xem bằng file Excel `data/exports/quality_review_20261112.xlsx`.

| Luật | Xử lý | Lần chạy 12/11/2026 |
|---|---|---:|
| Câu hỏi có `score <= -5` | Loại (`SCORE_TOO_LOW`) | 286 |
| Ngôn ngữ (câu có chữ không phải Latin) | **Không lọc**. Đọc mẫu thì đều là câu tiếng Anh dùng chữ nước ngoài làm ví dụ, xem D14 | 0 |
| Câu hỏi trùng y hệt tiêu đề, chữ và code với câu khác | Giữ một bản, loại các bản còn lại (`DUPLICATE_TEXT`). Bản được giữ: bị đóng vì trùng, rồi nhiều câu trả lời hơn, rồi điểm cao hơn, rồi mới hơn (D14) | 19 |
| Comment trùng nội dung trong cùng một bài | Loại bản sau (`DUPLICATE_IN_POST`) | 72 |
| Câu hỏi bị đóng vì lý do khác "trùng" | Chỉ gắn cờ ở `closed_reason` (`CLOSED_NOT_AS_DUPLICATE`) | 1.517 |
| Body ngắn, chỉ có code | **Không lọc theo độ dài**, chỉ gắn cờ `CODE_ONLY`, `SHORT_TEXT` (D14) | |
| Người đăng đã xóa tài khoản | Chỉ gắn cờ (đã có từ bước chuẩn hóa) | |
| Comment ≤ 2 từ; hoặc comment ≤ 20 từ khớp mẫu "please edit/provide…", "welcome to Stack Overflow", "what have you tried", "minimal example"; hoặc câu mẫu tự sinh của hàng đợi duyệt bài ("Your answer could be improved…", "As it's currently written, your answer is unclear…") | Chỉ gắn cờ `is_low_info`, lý do ở `low_info_reasons` | xem `low_info_comments` trong `cleaning_stats.json` |
| Comment tự sinh "This question is similar to: [link]…" (bản mới của "Possible duplicate of…") | **Loại** ở bước 2 (lộ đáp án) | |

- Loại câu hỏi thì câu trả lời và comment của nó cũng bị loại ở bước "mồ côi" (lần chạy 12/11: 544 câu trả lời, 1.743 comment).
- **Khi có thêm dữ liệu:** chạy lại pipeline rồi xem `score_profile` trong `reports/cleaning_stats.json`. Bảng này tính **trước** khi lọc, cho mỗi nhóm điểm tỉ lệ câu bị đóng vì trùng, đóng vì lý do khác và không có code. Nếu nhóm `<= -5` không còn khác hẳn nhóm `>= 0` thì xem lại ngưỡng.
- **Số liệu:** số bài bị loại theo từng lý do nằm ở bước `quality` và `repeats` trong `cleaning_stats.json`.

### 5. Chuẩn hóa kiểu dữ liệu

- Đổi ngày từ số Unix sang UTC timestamp, chuẩn hóa tag (viết thường), ép kiểu theo data contract.
- Xử lý trường bị thiếu, ví dụ câu hỏi không có comment thì để `comment_count = 0` và `comments = []`.
- **Không tin `comment_count` của API.** Trong mẫu ngày 24/10 có 80 trên 991 câu hỏi có `comment_count > 0` nhưng endpoint comments trả về 0 comment. Gọi lại cũng vậy (ví dụ câu 79904105). Có thể comment đã bị xóa nhưng vẫn được đếm. Ngày 31/10/2026, API vẫn trả về câu 79904105 nhưng mở trên web thì bị chuyển sang `stackoverflow.com/staging-ground/79904105` và báo "Page not found", trong khi câu 38987 vẫn mở bình thường. Có thể những câu bị lệch `comment_count` là câu không còn xem được trên web, nhưng điều này chưa được kiểm chứng. Không dùng những câu này làm ví dụ trong báo cáo hay demo. Phải tính lại `comment_count` từ comment thực sự lấy được, và ghi con số lệch này vào mục Khó khăn của báo cáo.
- **Kiểm tra:** chạy validate theo schema. Fail thì dừng pipeline.

## Báo cáo số liệu

Mỗi lần chạy, pipeline ghi file `reports/cleaning_stats.json`. Với mỗi bước có: số bản ghi vào, ra, bị loại, lý do loại và 3 ví dụ trước/sau. Báo cáo cuối dùng trực tiếp file này cho mục "Khó khăn và giải pháp".

## EDA (sau khi làm sạch)

Do nhóm ETL làm. Kết quả và biểu đồ lưu trong `notebooks/eda.ipynb` và `reports/figures/`.

- Phân bố tag, độ dài body và comment, số comment trên mỗi câu hỏi.
- Tỉ lệ câu hỏi không có comment, chia theo câu bị đóng vì trùng và câu khác.
