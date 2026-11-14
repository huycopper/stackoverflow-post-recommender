# Nhật ký quyết định

Mỗi quyết định ghi: **ngày, quyết định, lý do, người chốt**. Không xóa mục cũ. Nếu thay đổi thì thêm mục mới ghi "thay thế Dx".

## Đã chốt

### D1. Đề tài: gợi ý bài viết dựa trên nội dung và comment (14/10/2026)
- **Quyết định:** làm hệ thống gợi ý top-K bài viết dùng nội dung và comment. Đã đăng ký qua form Project Registration DS ([01](01_project_brief.md)).
- **Lý do:** có câu hỏi nghiên cứu rõ ràng (comment có giúp ích không), có thể đánh giá định lượng, và bao được các bài giảng từ crawl tới evaluation.
- **Người đề xuất:** Hung. Ý tưởng recommender system ban đầu là của Huy Copper (11/10). Cả nhóm đồng ý.

### D2. Nguồn dữ liệu: Stack Overflow thay cho Facebook/Reddit (14/10/2026)
- **Quyết định:** dùng Stack Overflow.
- **Lý do:** có sẵn quan hệ câu hỏi trùng để làm nhãn đúng. Subreddit chỉ là nhãn yếu, vì một subreddit có nhiều chủ đề, còn bài liên quan lại có thể nằm ở các subreddit khác nhau. Gán nhãn bằng LLM thì tốn chi phí.
- **Người đề xuất:** Nguyễn Huy. Hung đồng ý.

### D3. Các câu trả lời của TA (16/10/2026)
- Pháp lý không phải tiêu chí chấm. Cách thu thập nào cũng được. **Bắt buộc có bước làm sạch thật sự**, nếu không sẽ bị trừ khoảng 20%. Khi trình bày phải nêu khó khăn với dữ liệu. Chi tiết ở [02](02_course_requirements.md).

### D4. Phân công theo tỉ lệ 2 – 1 – 2 (17/10/2026)
- **Quyết định:** 2 người ETL kiêm EDA, 1 người nghiên cứu và viết code model, 2 người training và viết báo cáo. Xem [08](08_team_workflow.md).
- **Lý do (Hung):** có AI hỗ trợ thì khối lượng của 1 người làm model tương đương 2 người làm ETL. Training tốn thời gian vì phải treo máy rồi mới đọc kết quả và sửa.

### D5. Lấy dữ liệu qua API chính thức của Stack Exchange, không lách chống bot (19/10/2026)
- **Quyết định:** dùng `api.stackexchange.com`. Không scrape HTML và không bypass Cloudflare bằng giả cookie hay fingerprint.
- **Lý do:** stackoverflow.com bị Cloudflare chặn. Lách chống bot vừa khó vừa không nên làm. TA xác nhận gọi API được tính là bước thu thập. Dữ liệu API vẫn là HTML thô nên vẫn đủ việc làm sạch ([05](05_cleaning_pipeline.md)).
- **Người đề xuất:** Huy Copper. Hung đồng ý.

### D6. Repo chung mới (23/10/2026)
- **Quyết định:** dùng repo `huycopper/stackoverflow-post-recommender` làm repo chung, bắt đầu từ đầu. Repo `44444huy/DataScience_20261` không dùng nữa.
- **Người chốt:** Huy Copper.

### D7. Thiết kế bộ thu thập (24/10/2026)
- **Quyết định:** bộ thu thập chỉ dùng thư viện chuẩn của Python. Lấy mẫu theo thứ tự seed (câu vote cao) → linked (câu trùng trỏ tới seed) → background → originals → answers/comments. Lưu raw nguyên văn, data contract lên 0.2 cho lớp raw.
- **Lý do:** ai cũng chạy được mà không cần cài thêm. Đi từ các câu hỏi "kinh điển" cho ra nhiều cặp trùng với ít request. Chi tiết ở [03](03_data_source.md).
- **Người làm:** Huy Copper.

### D8. Không cắt câu trả lời và comment (24/10/2026)
- **Quyết định:** batch câu trả lời và comment được gom theo `answer_count`/`comment_count` (khoảng 500 mục mỗi batch) và lấy hết mọi trang. Thêm lệnh `repair` để lấy bù dữ liệu cũ bị thiếu.
- **Lý do:** cách cũ (100 ID, tối đa 5 trang) làm mẫu ngày 24/10 chỉ có 4.120 trên 9.222 câu trả lời. Cấu hình `C+Cm` cần comment của câu trả lời đầy đủ, còn báo cáo cần số liệu đúng.
- **Người làm:** Huy Copper.

### D9. Định dạng đầu vào model (23/10/2026)
- **Quyết định:** dữ liệu đưa cho bên model là một **mảng JSON**, mỗi phần tử gồm `title`, `body`, `comments` (danh sách chuỗi) và `tags` (danh sách chuỗi). Ghi trong data contract 0.3 ([04](04_data_contract.md), mục 3).
- **Lý do:** bên model cần một định dạng thống nhất để mỗi bên làm một phần ("thống nhất format data dùng cho model xong mỗi bên làm 1 thành phần").
- **Người chốt:** Hung (nhóm Messenger, 23/10/2026 20:37). ETL đề xuất thêm `question_id`, `split`, `answers` và file nhãn `qrels.json`, đang chờ Hung xác nhận.

### D10. Thu thập càng nhiều càng tốt, chạy tự động mỗi ngày (25/10/2026)
- **Quyết định:** tăng `seed_pages_per_tag` lên 100 và chạy bộ thu thập lúc 22:00 mỗi ngày bằng Task Scheduler trên máy Huy Copper ([03](03_data_source.md#chạy-tự-động-mỗi-ngày)). Việc làm sạch để sau, khi Huy Copper và Nguyễn Huy đã xem dữ liệu và tìm insight.
- **Lý do:** Hung chưa biết cần bao nhiêu dữ liệu, và đề xuất "chạy crawl tự động, cho hết data thô vào 1 chỗ rồi viết code xử lý song song". Quota giới hạn 10.000 request/ngày nên phải chạy qua nhiều ngày.
- **Người chốt:** Huy Copper, theo đề xuất của Hung.

### D11. Dừng thu thập, chuyển sang khám phá dữ liệu (26/10/2026)
- **Quyết định:** dừng ở 100 trang seed (93.704 câu hỏi, 23.470 cặp trùng) và tắt lịch 22:00 (Disabled, chưa xóa). Xuất dữ liệu ra `data/flat/*.parquet` và một file Excel thống kê kèm mẫu, để Huy Copper và Nguyễn Huy xem rồi thống nhất các bước làm sạch.
- **Lý do:** dữ liệu đã đủ cho đề tài, với khoảng 20 nghìn câu trùng làm query. Các bước làm sạch cần được chọn dựa trên insight từ dữ liệu thật ([05](05_cleaning_pipeline.md)).
- **Người chốt:** Huy Copper.

### D12. Nguyễn Huy phụ trách khám phá dữ liệu và làm sạch (26/10/2026)
- **Quyết định:** từ 26/10, Nguyễn Huy làm tiếp phần xem dữ liệu, tìm insight, chốt và cài đặt các bước làm sạch ([05](05_cleaning_pipeline.md)). Đầu vào là `data/flat/*.parquet` và `data/exports/explore_20261026.xlsx` từ D11.
- **Lý do:** Huy Copper đã làm xong phần thu thập và xuất dữ liệu. Nguyễn Huy nhận làm tiếp phần làm sạch.
- **Người chốt:** Nguyễn Huy và Huy Copper.

### D13. Chỉ làm sạch và EDA: bỏ ánh xạ câu trùng và việc chia tập (05/11/2026)
- **Quyết định:** phần việc này dừng ở làm sạch và EDA. Pipeline không còn tạo `duplicate_pairs`, `duplicate_groups`, `splits`, `qrels.json` và trường `split`. Đầu ra là `questions`, `answers`, `comments`, `rejected/` và `documents` ở cả hai dạng `documents.json`, `documents.parquet`. Data contract lên 0.4 ([04](04_data_contract.md)). Thay thế phần "chia theo nhóm trùng" và file nhãn đề xuất trong D9.
- **Lý do:** việc chia train/val/test và phần model do người khác phụ trách.
- **Hệ quả:**
  - Ánh xạ câu trùng tới câu gốc vẫn lấy lại được từ `closed_details.original_questions` trong `data/raw/` ([10](10_raw_data_metadata.md)). Code cũ nằm trong lịch sử git.
  - Vẫn giữ bước lọc comment "Possible duplicate of…", cột `is_closed_duplicate` và `closed_reason`.
  - `documents.parquet` xuất song song với `documents.json` (định dạng D9) cho tới khi chốt một định dạng.
- **Người chốt:** Nguyễn Huy.

### D14. Lọc chất lượng: loại câu hỏi score ≤ −5 (12/11/2026)
- **Quyết định:** bước lọc chất lượng ([05](05_cleaning_pipeline.md), bước 4) loại câu hỏi có `score <= -5`. Ngưỡng ở `config/clean.toml`, mục `[quality]`.
- **Lý do (số liệu lần chạy 12/11/2026, 93.704 câu trước khi lọc):**

  | Nhóm score | Số câu | Đóng vì trùng | Đóng vì lý do khác | Không có code |
  |---|---:|---:|---:|---:|
  | ≤ −5 | 286 | 43% | 21,3% | 24% |
  | −4 đến −1 | 8.669 | 41% | 5,8% | 18% |
  | ≥ 0 | 84.749 | 19% | 1,1% | 18% |

  - Câu ≤ −5 bị đóng vì lý do khác "trùng" (thiếu chi tiết, không hợp với trang, hỏi quá rộng) nhiều gấp khoảng 20 lần câu điểm không âm. Đây phần nhiều là câu hỏi kém thật.
  - Câu điểm âm nói chung có tỉ lệ là câu trùng gấp đôi, vì người hỏi không tự tìm trước. Hạ ngưỡng xuống −3 (loại 1.643 câu) hay −1 (8.955 câu) sẽ loại nhiều chính loại câu mà đề tài quan tâm, nên chỉ loại nhóm bị chê rất nặng.
- **Khi có thêm dữ liệu:** pipeline tự tính lại bảng trên ở `score_profile` trong `reports/cleaning_stats.json` (trước khi lọc). Xem lại ngưỡng nếu các tỉ lệ thay đổi nhiều.
- **Không lọc theo ngôn ngữ.** Có 97 câu chứa chữ không phải Latin (Nga, Trung, Nhật, Hàn, Ả Rập). Đọc mẫu trong file Excel và trên web thì đều là câu tiếng Anh, chữ nước ngoài chỉ là ví dụ trong nội dung (xử lý Unicode, xóa dấu tiếng Ả Rập, lỗi encoding). Luật thử "≥ 20% chữ không phải Latin" bắt 4 câu và cả 4 đều là câu tiếng Anh, tức chỉ bắt nhầm. Stack Overflow bản tiếng Anh bắt buộc viết tiếng Anh (các thứ tiếng khác có trang riêng như ru.stackoverflow.com). Cũng không sửa ký tự trong văn bản (đổi chữ Nga trông giống Latin, chuẩn hóa NFKC): từ lẫn hai loại chữ chỉ có ở 50 câu và phần lớn là tiếng Việt, ký hiệu toán học; còn NFKC đổi cả `x²` thành `x2`. Nếu lần crawl sau có câu nước ngoài thật thì thêm một bộ nhận diện ngôn ngữ chung, không thêm luật cho từng thứ tiếng.
- **Câu hỏi trùng y hệt: giữ bản tốt hơn, không giữ bản đăng trước.** Có 20 nhóm câu cùng tiêu đề và chữ. Cả 20 đều là người hỏi đăng lại câu của mình sau vài giờ đến vài ngày: bản đăng trước luôn có 0 câu trả lời và điểm 0, bản đăng lại thường có câu trả lời, 3 bản đăng lại bị đóng vì trùng. Câu 78839271 (bản đăng trước) mở trên web báo "Page not found" (12/11/2026), dù API vẫn trả về cả 40 câu. Vì vậy bản được giữ là bản bị đóng vì trùng, rồi bản có nhiều câu trả lời hơn (`answer_count` của API), rồi điểm cao hơn, rồi bản mới hơn. Phải giống cả code: 1 nhóm có chữ giống nhưng code khác nên không bị tính là bản sao.
- **Không lọc theo độ dài câu hỏi.** Câu ngắn thường dồn ý vào tiêu đề và code (105 câu chỉ có code, 84 câu có 1–4 từ kèm code), câu dài chỉ là kể chi tiết hơn; đọc mẫu thì cả hai đều là câu hỏi hợp lệ. Câu kém thật đã được cộng đồng chấm âm hoặc đóng, và đã có luật riêng cho hai trường hợp đó. Chỉ giữ cờ cảnh báo `CODE_ONLY`, `SHORT_TEXT` từ bước chuẩn hóa. Câu không có chữ lẫn code thì vẫn loại (`EMPTY_BODY`, 0 câu trong lần chạy này).
- **Câu bị đóng vì lý do khác "trùng": chỉ gắn cờ** (`CLOSED_NOT_AS_DUPLICATE` ở `closed_reason`), không loại. Nhóm này lẫn hai loại rất khác nhau: "Needs details or clarity" (308 câu, điểm trung vị −1, lượt xem trung vị 237) là câu kém, còn "Opinion-based" và các lý do cũ trước khoảng 2013 như "not constructive" (284 câu, điểm trung vị 22–97, lượt xem trung vị 26.000–77.000) là những câu nổi tiếng bị đóng khi luật của trang thay đổi. 92–100% câu trong nhóm có câu trả lời. Câu kém nặng nhất đã bị luật score ≤ −5 loại.
- **Bài của tài khoản không còn tồn tại (`owner.user_type = does_not_exist`): chỉ gắn cờ.** Điểm, tỉ lệ trùng, tỉ lệ có câu trả lời, lượt xem, tỉ lệ được chấp nhận đều gần như giống các bài khác. API không phân biệt được người dùng tự xóa hay bị xóa; tên hiển thị dạng "user12345" cũng không có nghĩa là tài khoản đã xóa (đó có thể chỉ là tên mặc định).
- **Link trong comment tới câu hỏi hoặc câu trả lời khác thay bằng `[link]`** ([05](05_cleaning_pipeline.md), bước 2). Chữ của link thường là tiêu đề câu được trỏ tới; 2.306 trên 19.979 câu trùng (11,5%) có comment trỏ thẳng tới câu gốc, nên `C+Cm` sẽ chứa sẵn đáp án. Thay cho mọi comment như nhau để bước làm sạch không cần dùng ánh xạ câu trùng (D13); không xóa cả comment để giữ phần chữ người dùng tự viết. Cùng lúc sửa lỗi luật lọc comment lộ đáp án: so mẫu trên nội dung đã bỏ thẻ HTML (84 comment kiểu "Does <a…>this</a> answer your question?" từng lọt qua).
- **Mở rộng luật thay link (13/11/2026):** áp cho cả body câu hỏi và body câu trả lời, và cho link tới mọi trang Stack Exchange (meta.stackoverflow.com, superuser.com, *.stackexchange.com...). Đo ngày 13/11: 13.487 câu hỏi (14,4%) có link trong body, trong đó 301 câu trùng trỏ thẳng tới câu gốc của nó; 32.366 câu trả lời (12,6%) có link. Link trong body nằm trong cả `C` lẫn `C+Cm`, nên không thay thì cả hai cấu hình đều có thể chứa sẵn tiêu đề câu gốc. Link meta không lộ đáp án nhưng là nhiễu (tên miền và dãy số, nhiều câu không liên quan dẫn cùng một trang hướng dẫn). Code trong khối `<pre>` giữ nguyên.
- **Comment chỉ có link sang câu hỏi khác: loại** (`ONLY_LINK`). Ở dữ liệu ngày 05/11, 1.684 trên 3.515 comment chỉ có 1 từ là một URL Stack Overflow trần. Sau khi thay link, các comment này chỉ còn `[link]`, không còn nội dung, nên xử lý như comment rỗng (khoảng 2.000 comment). Comment chỉ có link ra ngoài Stack Overflow (github, blog...) thì giữ, có cờ `is_low_info`.
- **Cờ `is_low_info` giữ là cờ, không loại**, và ghi thêm cột `low_info_reasons` (`SHORT` hoặc tên mẫu câu khớp) để người dùng dữ liệu lọc được từng loại. Lý do: comment kiểu "please edit your question to provide…" giống nhau ở hàng nghìn câu hỏi không liên quan và không mô tả vấn đề, nên có thể tạo độ giống giả khi đưa comment vào model. Đây là giả thuyết; gắn cờ để so sánh được kết quả khi giữ và khi bỏ chúng.
- **`documents` có thêm `comments_low_info`** (13/11/2026): danh sách nhãn `is_low_info` song song với `comments`, để bên dùng `documents` thử được việc bỏ comment ít thông tin mà không phải ghép lại từ `comments.parquet`. Chỉ thêm trường, không đổi hay xóa trường cũ.
- **Mẫu câu chỉ tính khi comment ≤ 20 từ** (13/11/2026). Mẫu "asks for details" khớp 11.699 comment, trung vị 22 từ; đọc mẫu theo độ dài thì comment ≤ 20 từ hầu như chỉ đòi thêm chi tiết, còn comment dài hơn thường có góp ý thật phía sau câu "Can you…" (ví dụ "Can you give the output of echo $SHELL. I suspect that your shell does not load ~/.bashrc…"). Câu mẫu tự sinh của hàng đợi duyệt bài thì gắn cờ ở mọi độ dài.
- **Thêm "This question is similar to" vào danh sách comment lộ đáp án** (374 comment): đây là bản mới (từ khoảng 2024) của comment tự sinh "Possible duplicate of…".
- **Xóa khung "Possible Duplicate:" cũ ở đầu body câu hỏi** (13/11/2026). Trước khoảng 2013, Stack Overflow tự chèn vào đầu body câu bị đóng vì trùng một khung trích dẫn "Possible Duplicate: <link câu gốc>". Trong 109 body có cụm "possible duplicate" hoặc "this question already has", 79 là khung này và bị xóa (cờ `DUPLICATE_BANNER_REMOVED` ở `body_text`). 30 câu còn lại là người hỏi tự viết (ví dụ "Edit: I don't think this is a possible duplicate of…") nên giữ. Khung này không phải chữ người hỏi viết, và vẫn báo hiệu câu là câu trùng dù link đã thành `[link]`.
- **Comment lặp trong cùng một bài: loại bản sau, giữ comment có id nhỏ nhất** (147 comment, 0,02%). 81% là cùng một người viết, phần lớn cách nhau ≤ 10 phút: hoặc bấm gửi hai lần, hoặc dẫn liền nhiều link "Related: [link]" mà sau khi thay link thì giống hệt nhau (vì vậy số comment lặp tăng từ 72 lên khoảng 150 sau bước thay link). Bỏ một bản không làm mất chữ nào của bài, lại tránh một cụm chữ bị tính nhiều lần.
- **Người chốt:** Nguyễn Huy.

## Câu hỏi mở

| # | Câu hỏi | Ai chốt | Trạng thái |
|---|---|---|---|
| Q1 | Báo TA việc đổi nguồn sang Stack Overflow, Stack Overflow có tính là "social media" không | ? | Chưa hỏi lại |
| Q2 | Lưu trữ: Python + Parquet/SQL, hay lakehouse/Spark | Nguyễn Huy | Đang cân nhắc. Đề xuất Python ([06](06_architecture.md#lưu-trữ)) |
| Q3 | Phạm vi tag: `python`, hay thêm `pandas`, hay tag khác | ETL | Chỉ `python`. 10 trang seed (24/10), rồi tăng lên 100 trang (25/10, D10). Muốn thêm tag thì thêm vào `config/collect.toml`, lịch hằng ngày sẽ lấy tiếp |
| Q4 | Data contract lên 1.0 | ETL + Hung | Hung đã gửi định dạng (D9). Còn chờ Hung trả lời các trường bổ sung và cách lưu nhãn ([04](04_data_contract.md#câu-hỏi-mở-cần-chốt-với-bên-model)) |
| Q5 | Ai làm phần "Training + viết báo cáo" | Nam, Hoàng | Chưa chọn |
| Q8 | Giữ `documents.json`, `documents.parquet`, hay cả hai | Nhóm | Đang xuất song song (D13) |
