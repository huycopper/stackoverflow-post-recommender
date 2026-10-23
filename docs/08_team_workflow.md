# 08. Phân công và cách làm việc

## Phân công

Theo cuộc thăm dò "Chọn việc làm" trong nhóm Messenger (tạo 17/10/2026). Hung đề xuất chia **2 – 1 – 2**.

| Phần việc | Người | Phụ trách thư mục |
|---|---|---|
| ETL + EDA: thu thập, làm sạch, tích hợp, EDA | Huy Copper, Nguyễn Huy | `src/so_recommender/collect`, `clean`, `features`, `notebooks/eda*` |
| Nghiên cứu model, viết code model, viết kiến thức nền | Hung Tran | `src/so_recommender/models`, `evaluate` |
| Training, ghi số liệu, đánh giá, viết báo cáo | *chưa có người* (Nam, Hoàng chưa chọn) | `results/`, `reports/` |

Chia việc trong nhóm ETL (đề xuất, cần thống nhất):

- **Huy Copper:** bộ thu thập qua API và dữ liệu thô.
- **Nguyễn Huy:** 6 bước làm sạch, lưu trữ.
- **EDA:** hai người chia nhau.

Mỗi dòng trên tương ứng một mục trong [09_roadmap.md](09_roadmap.md). Ai nhận mục nào thì ghi tên vào đó.

## Nhánh và PR

- `main` luôn chạy được. **Không push thẳng vào `main`**, mọi thay đổi đi qua PR.
- Tên nhánh: `etl/<việc>`, `model/<việc>`, `eval/<việc>`, `docs/<việc>`. Ví dụ `etl/api-collector`.
- Mỗi PR cần **ít nhất 1 người khác duyệt**.
- PR sửa [04_data_contract.md](04_data_contract.md) cần **1 người ETL và 1 người bên model** duyệt.
- PR nhỏ, mỗi PR làm một việc. Điền đủ checklist trong mẫu PR.

## Commit

Theo Conventional Commits, viết bằng tiếng Anh:

```
feat(collect): fetch question comments in batches of 100
fix(clean): keep inline <code> as text
docs(contract): add text_answers field (v0.2)
```

## Quyết định và trao đổi

- Thảo luận ở nhóm Messenger. **Chốt gì thì ghi vào [decisions.md](decisions.md)**, kèm ngày và lý do. Thông tin chỉ nằm trong chat sẽ bị trôi mất.
- Việc cần làm và bug ghi vào GitHub Issues, gắn nhãn `etl`, `model`, `report`.

## Dùng AI để viết code

- Cho AI đọc [AGENTS.md](../AGENTS.md) trước. Claude Code tự đọc file này qua `CLAUDE.md`. Với công cụ khác, mở hoặc đính kèm `AGENTS.md`.
- Code do AI viết vẫn phải có test và được người khác review như code bình thường.
- Trong buổi thuyết trình, ai cũng phải giải thích được phần mình làm.
