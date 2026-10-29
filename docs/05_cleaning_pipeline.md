# 05. Làm sạch và tích hợp dữ liệu

Bước này chiếm khoảng **20% điểm**. Nếu dữ liệu sạch sẵn mà không có bước làm sạch, nhóm bị trừ ([02](02_course_requirements.md)). Vì vậy mỗi bước đều phải **có lý do, có số liệu và có ví dụ trước/sau** để đưa vào báo cáo.

Input: `data/raw/`, tức response nguyên văn dạng `.jsonl.gz`. Bản gửi qua Drive là file zip của thư mục này. **Không** dùng `data/flat/` làm đầu vào, vì bản đó chỉ để xem nhanh và đã tự khử trùng ([decisions](decisions.md), D15). Output: các bảng trong [04_data_contract.md](04_data_contract.md).

Giữ đủ mọi trường qua các bước làm sạch, vì EDA cần. Chỉ ở bước cuối mới trích các trường bên model cần (`documents.json`).

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

- Câu hỏi, câu trả lời, comment và quan hệ trùng đến từ các endpoint khác nhau, phải nối lại theo ID.
- Các trường hợp lệch cần xử lý:
  - Comment không tìm thấy bài cha.
  - Câu hỏi gốc chưa được lấy về: gọi bổ sung, hoặc bỏ cặp đó.
  - Một bài xuất hiện ở nhiều tag hoặc nhiều trang nên bị trùng bản ghi: khử trùng theo ID và giữ bản lấy mới nhất.
- **Số liệu:** số bản ghi trùng đã khử, số bản ghi mồ côi.

### 4. Xây nhãn đúng từ quan hệ trùng

- Quan hệ trùng **có hướng** (A trùng B) và **có thể nối tiếp** (A trùng B, B trùng C).
- Gộp các câu hỏi thành **nhóm** bằng thành phần liên thông của đồ thị trùng. Kết quả ghi ra `duplicate_groups`.
- Loại các cặp tự trỏ về chính nó.
- **Chia train/val/test theo nhóm**: cùng một nhóm không được nằm ở hai phía. Kết quả ghi ra `splits`.
- **Số liệu:** số nhóm, phân bố kích thước nhóm.

### 5. Lọc bài kém chất lượng

- Bài quá ngắn (ngưỡng chọn sau EDA), không phải tiếng Anh, điểm âm sâu, bài gần như giống hệt nhau, người đăng đã xóa tài khoản (`owner.user_type = "does_not_exist"`).
- Ngưỡng nào cũng phải ghi lại và giải thích lý do chọn.
- **Số liệu:** số bài bị loại theo từng lý do.

### 6. Chuẩn hóa kiểu dữ liệu

- Đổi ngày từ số Unix sang UTC timestamp, chuẩn hóa tag (viết thường), ép kiểu theo data contract.
- Nếu còn tag đồng nghĩa thì đổi sang tag chính, dùng bảng `data/flat/tag_synonyms.parquet` (`from_tag → to_tag`). Sheet Thống kê trong file Excel explore cho biết dữ liệu còn bao nhiêu tag như vậy.
- Xử lý trường bị thiếu, ví dụ câu hỏi không có comment thì để `comment_count = 0` và `comments = []`.
- **Không tin `comment_count` của API.** Trong mẫu ngày 24/10 có 80 trên 991 câu hỏi có `comment_count > 0` nhưng endpoint comments trả về 0 comment. Gọi lại cũng vậy (ví dụ câu 79904105). Có thể comment đã bị xóa nhưng vẫn được đếm. Phải tính lại `comment_count` từ comment thực sự lấy được, và ghi con số lệch này vào mục Khó khăn của báo cáo.
- **Kiểm tra:** chạy validate theo schema. Fail thì dừng pipeline.

## Báo cáo số liệu

Mỗi lần chạy, pipeline ghi file `reports/cleaning_stats.json`. Với mỗi bước có: số bản ghi vào, ra, bị loại, lý do loại và 3 ví dụ trước/sau. Báo cáo cuối dùng trực tiếp file này cho mục "Khó khăn và giải pháp".

## EDA (sau khi làm sạch)

Do nhóm ETL làm. Kết quả và biểu đồ lưu trong `notebooks/eda.ipynb` và `reports/figures/`.

- Phân bố tag, độ dài body và comment, số comment trên mỗi câu hỏi.
- Tỉ lệ câu hỏi không có comment, chia theo nhóm trùng và nhóm nền.
- Kích thước các nhóm trùng, số câu gốc trên mỗi câu trùng.
- Độ trùng từ vựng giữa câu trùng và câu gốc, so sánh khi chỉ dùng nội dung và khi có thêm comment. Đây là gợi ý ban đầu cho câu hỏi nghiên cứu.
