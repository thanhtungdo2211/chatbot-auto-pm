

# 🧠 **KỊCH BẢN CHATBOT HỖ TRỢ MANAGER (4 SESSION)**

*(Cho hệ thống Plane + LLM + RAG + Multi-Agent)*

---

# ✅ **SESSION 1 – TẠO PROJECT TỪ FILE**

### 🎯 **Mục tiêu**

* Người dùng upload file (Excel/Word/PDF/JSON).
* LLM phân tích → trích xuất → chuẩn hóa JSON.
* Đẩy Project + Task lên Plane.

---

## **Hội thoại mẫu**

**User:** “Tôi muốn tạo project từ file này.”
→ Upload file

**Bot:**

> 👍 Đã nhận file.
> Đang trích xuất thông tin dự án…

**Bot (sau khi extract JSON):**

> Đây là thông tin dự án tôi trích xuất được:
>
> * Tên dự án: …
> * Mô tả: …
> * Danh sách task: …
>
> Bạn có muốn tạo dự án này trên Plane không?

**User:** “Có.”

**Bot:**

> 🎉 Dự án đã được tạo thành công trên Plane!
> Mã dự án: XXX
> Tổng số task: 12

---

## **Logic xử lý**

### 1. **Nhận file → LLM Extract**

* Dùng prompt chuẩn: *PROMPT_PLANE_EXTRACT*
* Output: `{ is_info_project, project, tasks }`

### 2. **Kiểm tra**

* Nếu `is_info_project = false` → Bot hỏi lại:

  > “File không chứa project. Bạn mô tả rõ hơn nội dung giúp tôi?”

### 3. **Xác nhận trước khi tạo**

* Nếu user chưa đồng ý → không tạo.

### 4. **Gọi API Plane**

* `/projects/`
* `/projects/{id}/tasks/`

---

---

# ✅ **SESSION 2 – HỎI ĐÁP (QA) DỰA TRÊN PLANE + RAG**

### 🎯 **Mục tiêu**

* Lấy dữ liệu project/task/member từ Plane
* Index vào vector DB
* Dùng RAG trả lời bất kỳ câu hỏi nào

---

## **Hội thoại mẫu**

**User:** “Trong project AI2School còn bao nhiêu task chưa làm?”
**Bot:**

> Để mình kiểm tra…

→ Bot gọi API Plane, chạy RAG

**Bot:**

> Dự án AI2School hiện có:
>
> * 5 task chưa làm
> * 12 task đang tiến hành
>
> Bạn có muốn xem chi tiết không?

---

## **Logic RAG**

1. Khi user hỏi → gọi API Plane lấy dữ liệu mới nhất
2. Chunk dữ liệu (project, tasks, member, comment)
3. Cho vào Qdrant/Chroma
4. LLM xử lý theo template RAG

---

---

# ✅ **SESSION 3 – CẬP NHẬT THÔNG TIN**

### 🎯 **Mục tiêu**

* LLM trích xuất thông tin cần cập nhật
* Check xem đủ thông tin chưa
* Nếu thiếu → yêu cầu người dùng bổ sung
* Nếu đủ → hỏi lại user để xác nhận
* Sau đó cập nhật lên Plane

---

## **Hội thoại mẫu**

**User:**
“Cập nhật deadline task *Viết API Quiz* sang ngày 30/11.”

**Bot:**

> Tôi hiểu yêu cầu:
>
> * Task: *Viết API Quiz*
> * Trường cập nhật: deadline
> * Giá trị mới: 30/11
>
> Bạn có xác nhận cập nhật không?

**User:** “Có.”

**Bot:**

> ⏳ Đang cập nhật…
>
> ✔ Task đã được cập nhật thành công!

---

## ❗ Khi thiếu thông tin

**User:** “Cập nhật task số 5 cho dự án AI2School.”

→ LLM nhận dạng thiếu trường cần cập nhật.

**Bot:**

> Bạn muốn cập nhật trường nào của task số 5?
>
> * Tên task
> * Mô tả
> * Assignee
> * Deadline
> * Priority
> * State
>   …

**User:** “Deadline.”

**Bot:**

> Bạn muốn đặt deadline mới là gì?

→ Sau khi đủ thông tin → Bot xác nhận → cập nhật.

---

## **Logic LLM**

1. LLM extract dữ liệu theo API Plane spec
2. Nếu thiếu → tạo JSON lưu lại dạng:

```json
{
  "missing_fields": ["deadline"],
  "available": {...}
}
```

3. Sau khi người dùng bổ sung → ghép lại → xác thực
4. Hỏi người dùng: “Bạn có muốn cập nhật không?”
5. Gọi API Plane

---

---

# ✅ **SESSION 4 – GIAO TASK (ASSIGNMENT INTELLIGENCE)**

### 🎯 **Mục tiêu**

* Người dùng yêu cầu giao task
* Bot lấy danh sách:

  * Tasks
  * Members
  * Load (số task mỗi người đang làm)
  * Skill (nếu có metadata)
* LLM phân tích → chọn người phù hợp nhất
* Bot gợi ý
* Người dùng xác nhận → bot cập nhật lên Plane

---

## **Hội thoại mẫu**

**User:**
“Giao 10 task mới cho project AI2School.”

**Bot:**

> Đang lấy danh sách task và member…

**Bot (sau LLM đánh giá):**

> Đây là gợi ý phân công tối ưu dựa trên tải công việc và chuyên môn hiện tại:
>
> * Nguyễn Văn A → 4 task
> * Trần B → 3 task
> * Minh C → 2 task
> * Huy D → 1 task
>
> Bạn có muốn giao task theo gợi ý này không?

**User:** “Ok, làm theo gợi ý.”

**Bot:**

> ✔ Tất cả task đã được giao thành công!

---

## **Logic phân công (LLM)**

### Input cho LLM:

```json
{
  "tasks": [...],
  "members": [...],
  "member_load": {...},
  "skills": {...}
}
```

### LLM xem xét:

* độ phù hợp skill
* workload
* deadline
* độ ưu tiên
* level của member

### Output:

```json
{
  "assignment": [
    {"task_id": 1, "member_id": 20, "reason": "Skill khớp, workload thấp"},
    ...
  ]
}
```

---

# 🎯 **TÓM TẮT DÒNG CHẢY CHO CẢ 4 SESSION**

| Session            | Input              | LLM làm gì              | Output                             |
| ------------------ | ------------------ | ----------------------- | ---------------------------------- |
| **1. Tạo Project** | File               | Extract → JSON          | Push lên Plane                     |
| **2. Hỏi đáp**     | Câu hỏi            | RAG + dữ liệu Plane     | Trả lời chính xác                  |
| **3. Cập nhật**    | Mệnh lệnh cập nhật | Extract + Validate      | Update Plane sau khi user xác nhận |
| **4. Giao task**   | Yêu cầu phân công  | Đánh giá member phù hợp | Update assignee trên Plane         |

