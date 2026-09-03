---
trigger: always_on
description: Tự động sử dụng GitNexus để phân tích kiến trúc mã nguồn trước khi lên kế hoạch hoặc lập trình.
---

# Quy tắc Phân tích Kiến trúc bằng GitNexus (GitNexus Code Intelligence)

Khi bắt đầu một công việc mới, lập kế hoạch triển khai (`implementation_plan.md`), tái cấu trúc hoặc viết mã nguồn trong dự án này:

1. **Kiểm tra chỉ mục GitNexus**: Chạy `gitnexus analyze` để cập nhật chỉ mục mã nguồn mới nhất của dự án.
2. **Khám phá Kiến trúc**: Sử dụng GitNexus để tra cứu call graph, các điểm đầu vào (entry points), luồng phụ thuộc và cấu trúc module.
3. **Áp dụng vào Kế hoạch**: Đưa các phát hiện kiến trúc từ GitNexus vào phần phân tích và phương án thiết kế trước khi thực hiện chỉnh sửa code.
