# Hướng dẫn cho AI agent

File này dành cho mọi AI coding agent (Claude Code, Codex, Cursor, Copilot…) làm việc trong repo. `CLAUDE.md` chỉ import file này, nên **sửa quy tắc ở đây, không sửa ở `CLAUDE.md`**.

## Trước khi làm bất kỳ việc gì

1. Đọc [docs/01_project_brief.md](docs/01_project_brief.md) và [docs/decisions.md](docs/decisions.md).
2. Đọc thêm theo loại việc:
   - Thu thập, làm sạch, EDA: [03_data_source](docs/03_data_source.md), [04_data_contract](docs/04_data_contract.md), [05_cleaning_pipeline](docs/05_cleaning_pipeline.md)
   - Model, đánh giá: [04_data_contract](docs/04_data_contract.md), [07_modeling_eval](docs/07_modeling_eval.md)
   - Cấu trúc code, thư viện: [06_architecture](docs/06_architecture.md)
3. Nếu yêu cầu của người dùng mâu thuẫn với docs, hỏi lại trước khi làm.

## Quy tắc bắt buộc

- **Không lách cơ chế chống bot.** Không giả cookie hay fingerprint, không bypass Cloudflare. Chỉ lấy dữ liệu qua API chính thức của Stack Exchange ([decisions.md](docs/decisions.md), D5).
- **Tôn trọng giới hạn của API:** đọc `quota_remaining`, chờ đủ `backoff` khi API yêu cầu, dừng trước khi hết quota.
- **Dữ liệu thô không được sửa.** `data/raw/` chỉ ghi thêm. Mọi bước làm sạch đọc từ raw và ghi sang `data/clean/`.
- **Không commit dữ liệu hoặc secret:** không commit `data/`, `.env`, API key, file model lớn.
- **Data contract là giao diện giữa các bên.** Muốn đổi tên, kiểu, ý nghĩa của trường trong [04_data_contract.md](docs/04_data_contract.md) thì phải tăng version, ghi changelog trong file đó và thêm một mục vào `decisions.md`.
- **Mỗi bước làm sạch phải ghi lại số liệu** (số dòng vào, ra, bị loại, lý do). Báo cáo cần các số này ([02_course_requirements](docs/02_course_requirements.md)).
- **Chia train/test theo nhóm bài trùng**, không chia theo từng câu hỏi lẻ, để tránh rò rỉ nhãn ([07_modeling_eval](docs/07_modeling_eval.md)).
- **Dùng thư viện hoặc model có sẵn thì ghi vào mục "Thư viện sử dụng"** trong [06_architecture.md](docs/06_architecture.md). Môn học bắt buộc khai báo.

## Quy ước code

- Python 3.11 trở lên. Code, comment, docstring, commit message viết bằng **tiếng Anh**. Docs viết bằng tiếng Việt.
- Viết test bằng `pytest` cho mỗi hàm parse hoặc làm sạch. Lint bằng `ruff`.
- Đường dẫn và tham số để trong file config, không hard-code.
- Commit theo Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`). Xem [08_team_workflow.md](docs/08_team_workflow.md).

## Khi xong một việc

- Cập nhật docs liên quan nếu hành vi, định dạng hoặc cách chạy thay đổi.
- Đánh dấu checklist trong [09_roadmap.md](docs/09_roadmap.md) nếu hoàn thành một mục.
- Có quyết định mới (chọn công nghệ, đổi phạm vi…) thì ghi vào [decisions.md](docs/decisions.md).

## Giao tiếp

Trả lời người dùng bằng tiếng Việt, trừ khi họ viết bằng ngôn ngữ khác.
