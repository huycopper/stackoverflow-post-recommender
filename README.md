# Stack Overflow Post Recommender (Content + Comments)

Capstone project môn **Introduction to Data Science (IT4142E)**, HUST, học kỳ 2026.1.

Hệ thống gợi ý **top-K câu hỏi Stack Overflow liên quan nhất** cho một câu hỏi đầu vào, và trả lời câu hỏi nghiên cứu:

> Thêm thông tin từ **comment** có giúp gợi ý tốt hơn so với chỉ dùng **nội dung bài viết** không?

Nhãn đúng lấy từ quan hệ **câu hỏi trùng (duplicate)** trên Stack Overflow. Đánh giá bằng Precision@K, Recall@K, NDCG@K.

**Trạng thái (23/10/2026):** giai đoạn thu thập dữ liệu. Chưa có code. Xem [docs/09_roadmap.md](docs/09_roadmap.md).

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

Chưa có code. Phần này sẽ cập nhật khi có bộ thu thập dữ liệu đầu tiên. Dự kiến:

```bash
cp .env.example .env    # điền STACKEXCHANGE_KEY
python -m venv .venv
```
