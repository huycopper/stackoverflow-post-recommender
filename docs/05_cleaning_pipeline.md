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
- Loại comment chỉ chứa link tới một câu hỏi khác trên Stack Overflow.
- **Lý do:** nếu giữ lại, model `C+Cm` sẽ "nhìn thấy đáp án" và kết luận về vai trò của comment sẽ sai.
- **Số liệu:** số comment bị loại theo từng mẫu.

### 3. Ghép dữ liệu từ nhiều endpoint (data integration, bài L3)

- Câu hỏi, câu trả lời và comment đến từ các endpoint khác nhau, phải nối lại theo ID.
- Các trường hợp lệch cần xử lý:
  - Comment không tìm thấy bài cha.
  - Một bài xuất hiện ở nhiều tag hoặc nhiều trang nên bị trùng bản ghi: khử trùng theo ID và giữ bản lấy mới nhất.
- **Số liệu:** số bản ghi trùng đã khử, số bản ghi mồ côi.

### 4. Lọc bài kém chất lượng

- Bài quá ngắn (ngưỡng chọn sau EDA), không phải tiếng Anh, điểm âm sâu, bài gần như giống hệt nhau, người đăng đã xóa tài khoản (`owner.user_type = "does_not_exist"`).
- Ngưỡng nào cũng phải ghi lại và giải thích lý do chọn.
- **Số liệu:** số bài bị loại theo từng lý do.

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
