# 06. Kiến trúc và công nghệ

## Luồng dữ liệu

```
Stack Exchange API
      │  collect (quota, backoff, resume)
      ▼
data/raw/            JSONL.gz, response nguyên văn, chỉ ghi thêm
      │  ├─ explore flatten ─► data/flat/*.parquet (chưa sạch, để khám phá) ─► explore excel
      │  clean + integrate (5 bước, xem 05)
      ▼
data/clean/          Parquet theo data contract (04)
      │  build documents
      ▼
documents.json, documents.parquet, reports/eda/
```

## Cấu trúc thư mục dự kiến

```
.
├── AGENTS.md, CLAUDE.md, README.md
├── docs/                 # context dự án (thư mục này)
├── config/               # *.toml: tag, đường dẫn, tham số API và làm sạch
├── src/so_recommender/
│   ├── collect/          # gọi API, lưu raw          (ETL)
│   ├── clean/            # 5 bước làm sạch, ghép documents (ETL)
│   └── eda/              # phân tích khám phá         (ETL)
├── notebooks/            # EDA, phân tích kết quả
├── tests/                # pytest
├── data/                 # KHÔNG commit (raw/, clean/)
├── results/              # experiments.csv (commit), checkpoint (không commit)
└── reports/              # cleaning_stats.json, figures/, báo cáo, slide
```

## Lưu trữ

**Chưa chốt** (câu hỏi mở trong [decisions.md](decisions.md)). Đề xuất: **Python + Parquet**, có thể thêm SQLite hoặc Postgres để truy vấn khi làm EDA.

- Dữ liệu dự kiến vài chục đến vài trăm nghìn dòng. Pandas hoặc Polars xử lý được, **chưa cần Spark**.
- Nếu muốn có phần "big data" (bài L8) cho báo cáo, có thể thêm một thí nghiệm phụ so sánh pipeline Python với Spark trên cùng dữ liệu. Không đặt Spark trên đường chính.

## Thư viện sử dụng

Môn học bắt buộc khai báo mọi thư viện, model và code có sẵn trong báo cáo và slide. **Thêm một dòng mỗi khi dùng thư viện mới.**

| Thư viện / model | Dùng cho | Phần |
|---|---|---|
| Python standard library (`urllib`, `gzip`, `json`, `tomllib`) | Gọi API, lưu raw, đọc config | collect |
| Stack Exchange API v2.3 | Nguồn dữ liệu | collect |
| pyarrow | Bảng Parquet và thống kê trong `explore` | explore |
| openpyxl | File Excel khám phá dữ liệu | explore |
| PySpark 3.5.3 (chạy trong Docker) | Làm sạch dữ liệu: khử trùng, chuẩn hóa, lọc, ghép bảng, ghi Parquet | clean |
| pandas | Đọc bảng sạch, tính thống kê và vẽ trong EDA | eda |
| matplotlib | Vẽ biểu đồ EDA | eda |
| scikit-learn | TF-IDF, SVD, k-means trong EDA | eda |
| tzdata | Dữ liệu múi giờ cho timestamp UTC trên Windows | explore |
| pytest | Test | dev |
| ruff | Lint, format | dev |
| uv | Quản lý môi trường | dev |
