# Stack Overflow Post Recommender (Content + Comments)

Capstone project môn **Introduction to Data Science (IT4142E)**, HUST, học kỳ 2026.1.

Hệ thống gợi ý **top-K câu hỏi Stack Overflow liên quan nhất** cho một câu hỏi đầu vào, và trả lời câu hỏi nghiên cứu:

> Thêm thông tin từ **comment** có giúp gợi ý tốt hơn so với chỉ dùng **nội dung bài viết** không?

Nhãn đúng lấy từ quan hệ **câu hỏi trùng (duplicate)** trên Stack Overflow. Đánh giá bằng Precision@K, Recall@K, NDCG@K.

**Trạng thái (24/10/2026):** giai đoạn thu thập dữ liệu. Đã có bộ thu thập qua API. Xem [docs/09_roadmap.md](docs/09_roadmap.md).

## Đọc gì trước

| Bạn là | Đọc |
|---|---|
| Thành viên mới, hoặc AI agent | [AGENTS.md](AGENTS.md), sau đó [docs/01_project_brief.md](docs/01_project_brief.md) |
| Làm ETL, EDA | [03_data_source](docs/03_data_source.md), [04_data_contract](docs/04_data_contract.md), [05_cleaning_pipeline](docs/05_cleaning_pipeline.md) |
| Làm model, training | [04_data_contract](docs/04_data_contract.md), [07_modeling_eval](docs/07_modeling_eval.md) |
| Viết báo cáo, slide | [02_course_requirements](docs/02_course_requirements.md), [decisions.md](docs/decisions.md) |

Toàn bộ tài liệu:

1. [01_project_brief.md](docs/01_project_brief.md): bài toán, input/output, phạm vi
2. [02_course_requirements.md](docs/02_course_requirements.md): yêu cầu và tiêu chí chấm của môn, các câu trả lời của TA
3. [03_data_source.md](docs/03_data_source.md): API Stack Exchange
4. [04_data_contract.md](docs/04_data_contract.md): định dạng dữ liệu, chỗ ETL và bên model thống nhất với nhau
5. [05_cleaning_pipeline.md](docs/05_cleaning_pipeline.md): các bước làm sạch
6. [06_architecture.md](docs/06_architecture.md): luồng dữ liệu, thư mục, công nghệ, thư viện
7. [07_modeling_eval.md](docs/07_modeling_eval.md): model, cách đánh giá
8. [08_team_workflow.md](docs/08_team_workflow.md): phân công, quy tắc nhánh, PR, commit
9. [09_roadmap.md](docs/09_roadmap.md): kế hoạch, mốc, checklist
10. [decisions.md](docs/decisions.md): nhật ký quyết định

## Thành viên

| Thành viên | Vai trò |
|---|---|
| Huy Copper | ETL + EDA |
| Nguyễn Huy | ETL + EDA |
| Hung Tran | Nghiên cứu model, viết code model |
| Nguyễn Quý Ngọc Nam | Chưa chọn |
| Lê Minh Hoàng | Chưa chọn |

Chi tiết phân công xem [docs/08_team_workflow.md](docs/08_team_workflow.md).

## Cài đặt

Cần Python 3.11 trở lên. Bộ thu thập chỉ dùng thư viện chuẩn của Python. Phần dev (pytest, ruff) cài bằng [uv](https://docs.astral.sh/uv/).

```bash
uv sync                 # tạo .venv, cài package và nhóm dev
cp .env.example .env    # điền STACKEXCHANGE_KEY (xin key ở StackApps, xem docs/03)
uv run pytest           # chạy test
uv run ruff check .     # lint
```

Không dùng uv thì chạy `python -m venv .venv`, kích hoạt venv rồi `pip install -e . pytest ruff`.

## Thu thập dữ liệu

Chạy từ thư mục gốc của repo. Cấu hình nằm ở [config/collect.toml](config/collect.toml).

```bash
uv run python -m so_recommender.collect run --max-requests 50   # chạy thử nhỏ
uv run python -m so_recommender.collect run                     # chạy đủ; chạy lại để tiếp tục
uv run python -m so_recommender.collect summary --out reports/collect_summary.json
```

- Dữ liệu thô được ghi vào `data/raw/`, tiến độ ghi vào `data/collect_state.json`. Cả thư mục `data/` không commit.
- Muốn lấy một mẫu nhỏ để xem thử thì thêm `--config config/collect_sample.toml`. Mẫu này chỉ lấy 1 trang `linked` mỗi batch và ghi riêng vào `data/sample/`.
- `summary` cho biết dữ liệu còn thiếu bao nhiêu so với số đếm của API (`answers.questions_missing_some`, `comments.on_*_expected`). Nếu thiếu, chạy `repair` để đưa phần thiếu lại vào hàng đợi, rồi chạy `run` để lấy bù:

  ```bash
  uv run python -m so_recommender.collect repair
  uv run python -m so_recommender.collect run --steps answers question_comments answer_comments
  ```
- Khi gần hết quota, bị API throttle hoặc bị ngắt (Ctrl+C), chương trình **tự dừng và lưu tiến độ**. Chạy lại đúng lệnh cũ để tiếp tục.
- Mỗi lúc chỉ được có **một** lần chạy dùng cùng một file state. Nếu đang có lần chạy khác thì lệnh mới dừng ngay, trả mã 3 (khóa nằm ở `data/collect_state.lock`).
- `--log-file data/logs/x.log` ghi log ra file thay vì ra màn hình.
- Chi tiết các bước và chiến lược lấy mẫu xem [docs/03_data_source.md](docs/03_data_source.md).

### Chạy tự động mỗi ngày (Windows)

Trên máy Huy Copper có một lịch Task Scheduler tên **"SO Recommender - daily collect"**. Lịch này chạy [scripts/collect_daily.ps1](scripts/collect_daily.ps1) lúc **22:00 mỗi ngày**, và chạy bù nếu lúc đó máy đang tắt. Log ghi ở `data/logs/collect_YYYYMMDD_HHMM.log`. Mã thoát của script: 0 là đã lấy xong hết, 2 là tạm dừng vì quota (hôm sau chạy tiếp), 3 là đang có lần chạy khác.

```powershell
Get-ScheduledTask -TaskName "SO Recommender - daily collect" | Get-ScheduledTaskInfo   # lần chạy gần nhất / tiếp theo
Start-ScheduledTask -TaskName "SO Recommender - daily collect"                          # chạy ngay
Disable-ScheduledTask -TaskName "SO Recommender - daily collect"                        # tạm tắt lịch
Unregister-ScheduledTask -TaskName "SO Recommender - daily collect"                     # xóa lịch
```

Máy khác muốn tạo lịch giống vậy thì xem lệnh `Register-ScheduledTask` trong [docs/03_data_source.md](docs/03_data_source.md#chạy-tự-động-mỗi-ngày).
