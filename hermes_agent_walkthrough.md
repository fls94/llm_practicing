# Học cách Hermes Agent hoạt động: ghi chép hỏi đáp

Ghi lại từ buổi hỏi đáp đọc source code `hermes-agent` (10/2026).
Số dòng trích dẫn đúng tại commit `3b043e1900`; code thay đổi thì có thể lệch.

Mục lục:
1. `run_agent.py` để làm gì
2. Facade là gì
3. Lộ trình học hệ thống agent
4. "Điểm vào" và "chỉ chuyển tiếp"
5. Vì sao `run_conversation` bị bọc thêm một lớp nữa
6. Vì sao `agent` không có chú thích kiểu
7. Đoạn đầu của `_run_conversation_turn`
8. Một lượt (turn) là gì
9. `build_turn_context`
10. Vì sao code hay nhắc "dùng lại" và "reset"
11. Prompt caching hoạt động thế nào

---

## 1. `run_agent.py` để làm gì?

`run_agent.py` định nghĩa **`AIAgent`**: lõi agent gọi tool, dùng chung cho CLI, gateway
(Telegram, Discord…), TUI, desktop app, cron và subagent.

- **Điểm vào cho một cuộc hội thoại:** `AIAgent(model=...)` rồi `agent.run_conversation(query)`
  hoặc `agent.chat(message)`.
- **Vòng đời phiên:** tạo/reset phiên (`reset_session_state`), ghi bộ nhớ
  (`commit_memory_session`), giải phóng client (`close`), xử lý ngắt (`is_interrupted`).
- **Chạy độc lập:** `main()` cho phép chạy một truy vấn từ dòng lệnh.

`AIAgent` được ghép từ khoảng 14 mixin (`TurnFacadeMixin`, `CompressionFacadeMixin`,
`SessionPersistenceMixin`…). Vòng lặp thật nằm trong `agent/turn_*.py` và `agent/conversation_loop.py`.

## 2. Facade là gì?

**Facade** là "cửa trước mỏng": nơi duy nhất bên ngoài import, còn việc thật làm ở chỗ khác.

```python
from run_agent import AIAgent      # bên ngoài chỉ biết cái này
agent = AIAgent(model="...")
agent.run_conversation("hello")    # không cần biết nó nằm ở agent/turn_facade.py
```

Trong repo này, các "god file" cũ (`run_agent.py`, `cli.py`, `gateway/run.py`…) được tách thành
**facade + siblings**: facade giữ tên công khai, mỗi sibling `<stem>_<topic>.py` lo một chủ đề.

Quy tắc đi kèm (`AGENTS.md`):
1. Hành vi mới đặt vào sibling, không đặt vào facade.
2. Tìm code theo chủ đề (`grep -rn "def name" agent/`), đừng đọc facade.
3. Sibling import facade *bên trong hàm* để tránh vòng import.
4. Test phải patch đúng chỗ code production đọc.
5. Không để lại alias re-export khi chuyển code nội bộ.

## 3. Lộ trình học: đừng đọc từ trên xuống

Khoảng 90% code production là xử lý trường hợp đặc biệt. Hiểu ý tưởng trước, rồi mới tìm nó trong code.

### Bước 1: Ý tưởng cốt lõi

```python
messages = [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_input}]

while True:
    response = llm.call(messages, tools=TOOL_SCHEMAS)    # 1. gọi model
    messages.append(response)

    if not response.tool_calls:                           # 2. không gọi tool → xong
        return response.content

    for call in response.tool_calls:                      # 3. chạy từng tool
        result = TOOLS[call.name](**call.arguments)
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    # 4. quay lại bước 1
```

| Khái niệm | Ý nghĩa |
|---|---|
| **messages** | Toàn bộ "trí nhớ" của lượt. Model không nhớ gì ngoài danh sách này. |
| **tool schema** | Mô tả JSON của tool, gửi kèm mỗi lần gọi API |
| **tool call** | Model yêu cầu "chạy tool X với tham số Y" thay vì trả lời bằng chữ |
| **vòng lặp** | Lặp đến khi model trả lời bằng chữ |

### Bước 2: Tìm 4 khái niệm đó trong Hermes

| Khái niệm | Vị trí |
|---|---|
| Điểm vào | `AIAgent.run_conversation` → `agent/turn_facade.py:22` (chỉ chuyển tiếp) |
| Vòng lặp thật | `agent/conversation_loop.py`: `_run_conversation_turn` (dòng 1555), `while` ở dòng 1656 |
| Gọi model | `agent/turn_api_call.py`: `perform_api_call` |
| Chạy tool | `agent/turn_tool_round.py`: `run_tool_round` |
| Trả lời cuối | `agent/turn_final_response.py`: `finish_text_response` |
| Đăng ký tool | `tools/registry.py`: `ToolRegistry` |
| System prompt | `agent/prompt_builder.py` |

### Bước 3: Đọc một tool đơn giản

`tools/clarify_tool.py` (201 dòng) và `tools/todo_tool.py` (336 dòng): xem tool khai báo schema
và handler thế nào (`registry.register(...)` ở cuối file).

### Bước 4: Theo dấu một request thật

```
python run_agent.py --query "list files in current directory" --verbose
```

Đặt breakpoint ở `perform_api_call` và `run_tool_round` để xem `messages` thay đổi qua từng vòng.

### Bước 5: Mở rộng dần

Nén context, memory và skills, subagent, gateway. Mỗi thư mục có `AGENTS.md`: đọc nó trước code.

## 4. "Điểm vào" và "chỉ chuyển tiếp"

- **Điểm vào:** hàm mà code bên ngoài gọi đầu tiên. Gateway (`gateway/run_turn.py:560`) và
  TUI (`tui_gateway/methods_prompt.py:1107`) đều gọi `agent.run_conversation(...)`.
- **Chỉ chuyển tiếp (forwarder):** `AIAgent.run_conversation` trong `turn_facade.py` không chạy
  vòng lặp. Nó làm việc "hành chính" (huỷ review nền, giành lease chống chạy chồng, đăng ký relay,
  metrics) rồi gọi `agent.conversation_loop.run_conversation` ở `turn_facade.py:148`.

```
Gateway / TUI / Desktop
        │  agent.run_conversation("xin chào")
        ▼
① turn_facade.py        ← lễ tân: ghi sổ, lấy số, kiểm tra không trùng lịch
        ▼
② conversation_loop.py  ← bác sĩ: vòng lặp gọi model ↔ chạy tool
        ▼
   kết quả quay về ① → dọn dẹp → trả cho Gateway
```

## 5. Vì sao `run_conversation` bị bọc thêm một lớp nữa?

Thực tế có **3 lớp**:

```
① AIAgent.run_conversation            turn_facade.py:22
      └─ ② run_conversation           conversation_loop.py:1717
            └─ ③ _run_conversation_turn   conversation_loop.py:1555   ← LOGIC GỐC
                  └─ while ... (dòng 1656)
```

Hàm ③ có khoảng 10 chỗ `return` sớm (timeout nén, Codex, preflight gate, hết retry, lỗi phản hồi,
xong tool round…). Lớp ② tạo **một cửa ra duy nhất** để mọi kết quả đều được hậu xử lý:
- `end_voice_turn_route`: trả model voice về model chính
- `export_current_turn_boundary`: đánh dấu lượt bắt đầu ở message nào
- `user_intervened`: người dùng có chen ngang không
- `_close_durable_failed_turn`: lượt lỗi thì ghi thêm một message assistant, tránh hai message
  `user` liền nhau trong lịch sử

| Lớp | Lo việc gì |
|---|---|
| ① | Hạ tầng bên ngoài lượt (lease, relay, metrics) |
| ② | Hậu xử lý kết quả, áp dụng cho mọi đường thoát |
| ③ | Vòng lặp agent |

Vòng lặp thật, rút gọn:

```python
while s.api_call_count < agent.max_iterations ...:
    begin_iteration / prepare_iteration
    assemble_api_request                      # ghép messages + tool schemas
    run_preflight_gate                        # context có quá dài không
    early_result = _run_api_retry_loop(agent, s)   # ← llm.call(...) (+ retry)
    normalize_model_response
    if s.assistant_message.tool_calls:
        run_tool_round(...)                   # chạy tool → lặp tiếp
    else:
        finish_text_response(...)             # trả lời xong
```

`_run_phase(foo, agent, s)` chỉ là helper: lấy biến từ `s` (`_LoopState`) truyền vào `foo`, rồi
chép kết quả ngược lại. Đọc nó đơn giản là "gọi `foo`".

## 6. Vì sao `agent` không có chú thích kiểu?

1. **Hàm được tách ra từ method của `AIAgent`.** `self` đổi thành `agent`; `self` vốn không ghi
   kiểu nên `agent` cũng không.
2. **Tránh vòng import.** `run_agent → turn_facade → conversation_loop`. Nếu `conversation_loop`
   import `run_agent` ở đầu file thì sinh circular import. (Có thể né bằng `if TYPE_CHECKING:`
   nhưng thư mục `agent/` không theo quy ước đó.)
3. **Repo không chạy mypy/pyright**, nên chú thích kiểu chỉ là tài liệu.

Mẹo đọc code:
- Gặp `agent.foo` thì tìm `self.foo =`: `grep -rn "self.foo\s*=" run_agent.py agent/ hermes_cli/`
- Hoặc thêm tạm `agent: "AIAgent"` với `if TYPE_CHECKING:` để IDE nhảy được đến định nghĩa
  (đừng commit).
- `s` là `_LoopState` (dataclass trong cùng file): xem nó để biết vòng lặp theo dõi những gì.

## 7. Đoạn đầu của `_run_conversation_turn`

Bốn việc chuẩn bị đầu lượt, đều **không thuộc logic cốt lõi**:

| Dòng | Mục đích |
|---|---|
| `_decode_inline_moa_turn` | Tách cấu hình MoA (Mixture of Agents) nhúng trong tin nhắn |
| Reset cờ nén context | Không để lượt này bị báo nhầm là "đã nén" do lượt trước |
| `begin_fast_mode_turn` | Mở cửa sổ fast mode (`/fast auto`, `/fast cold`) |
| `_try_refresh_env_client_credentials` | Dùng API key/base URL mới nếu `.env` vừa đổi; lỗi không làm hỏng lượt |

## 8. Một lượt (turn) là gì?

Mỗi tin nhắn người dùng tương ứng với **một lần gọi `_run_conversation_turn`**, nhưng bên trong
**model có thể được gọi nhiều lần**:

```
Người dùng: "đoạn này để làm gì"          ← bắt đầu 1 lượt
├─ vòng 1: model → tool_calls = [Bash(...)] → run_tool_round
├─ vòng 2: model đọc kết quả → trả lời bằng chữ → finish_text_response
Người dùng nhận câu trả lời
```

| Khái niệm | Nghĩa | Trong code |
|---|---|---|
| Lượt (turn) | 1 tin nhắn → câu trả lời cuối | 1 lần gọi `_run_conversation_turn` |
| Vòng (iteration) | 1 lần gọi model (+ chạy tool) | 1 vòng `while`, `s.api_call_count` |
| Phiên (session) | Cả cuộc trò chuyện | `agent.session_id`, SessionDB |

Lượt sau được gọi lại từ đầu, với `conversation_history` là toàn bộ messages cũ. Model "nhớ" được
là nhờ lịch sử gửi lại mỗi lần.

Lượt kết thúc khi model trả lời bằng chữ, hết `max_iterations`/`iteration_budget`, bị ngắt,
hoặc gặp lỗi không khôi phục được.

## 9. `build_turn_context` (`agent/turn_context.py:1030`)

Phần mở đầu của mỗi lượt. Trả về `TurnContext` (dòng 490), là đầu vào của vòng `while`:

| Trường | Ý nghĩa |
|---|---|
| `messages` | Lịch sử + tin nhắn mới; vòng lặp append tiếp vào đây |
| `active_system_prompt` | System prompt, để riêng, **không nằm trong `messages`** |
| `current_turn_user_idx` | Vị trí tin nhắn user của lượt này |
| `ext_prefetch_cache` | Kiến thức lấy từ bộ nhớ dài hạn |
| `plugin_user_context` | Ngữ cảnh do plugin thêm |

Các nhóm bước:
- **A. Dọn dẹp và gắn danh tính** (đọc lướt): safe stdio, `_turn_author`, khôi phục phiên bị xoay,
  refresh MCP tools, `turn_id`, reset trạng thái lượt trước, ghi log.
- **B. Tạo `messages`** ⭐: `messages = list(conversation_history)` (bản sao) + append tin nhắn user.
- **C. System prompt** ⭐: chỉ tạo **1 lần/phiên** (`_cached_system_prompt`), để bảo vệ prompt cache.
- **D. Lưu DB và nén context**: tạo dòng phiên trong DB *sau* khi có system prompt, *trước* khi nén;
  `run_turn_start_compaction` nén nếu quá dài.
- **E. Bộ nhớ và plugin** ⭐: `_memory_turn_start_and_prefetch` (dòng 903) tìm trong bộ nhớ dài hạn
  theo câu hỏi (RAG). Câu hỏi quá ngắn thì bỏ qua.
- **F. api_content sidecar**: mỗi tin nhắn user có hai phiên bản:
  ```python
  {"role": "user",
   "content":     "hôm nay làm gì?",                         # hiển thị, transcript
   "api_content": "hôm nay làm gì?\n\n[memory] [plugin]"}    # thứ thật sự gửi cho model
  ```
  `api_content` được lưu vào DB để lượt sau gửi lại đúng từng byte ("persist what you send").
- **G. Lưu và trả về**: `_persist_turn_start` ghi ngay phòng crash; đặt tiêu đề phiên ở luồng nền.

```
conversation_history ──┐
                       ├──► messages = [...lịch sử, {user: tin mới}]
user_message ──────────┘                 │
                            (quá dài?) → nén context
bộ nhớ dài hạn ─► prefetch ─┐            │
plugin hooks ───────────────┼──► gắn vào "api_content" của tin nhắn user
system prompt (1 lần/phiên) ─────────────┤
                                         ▼
                                   TurnContext ──► vòng while
```

Bước tiếp theo: `build_api_messages` (dòng 1237) biến `messages` thành request thật (ghép system
prompt, dùng `api_content`, bỏ trường nội bộ).

## 10. Vì sao code hay nhắc "dùng lại" và "reset"?

### Hệ thống nhìn từ trên xuống

```
  Telegram    Discord    Slack     ...
     ▼           ▼         ▼
┌──────────────────────────────────────────────────────────┐
│  GATEWAY (1 tiến trình chạy nhiều ngày)                   │
│   _agent_cache  (gateway/run_agent_cache.py)              │
│   │ telegram:An        │ 🤖 agent #1 │                    │
│   │ telegram:Bình      │ 🤖 agent #2 │                    │
│   │ discord:#general   │ 🤖 agent #3 │  (tối đa 128)      │
│   Không hoạt động > 1 giờ → xoá khỏi cache                │
└──────────────────────────────────────────────────────────┘
```

`gateway/run.py:51-52`: `_AGENT_CACHE_MAX_SIZE = 128`, `_AGENT_CACHE_IDLE_TTL_SECS = 3600`.
CLI cũng tạo `self.agent = AIAgent(...)` một lần cho cả phiên.

### Vì sao dùng lại

Tạo mới mỗi lượt thì chậm (tạo client, nạp tool, kết nối bộ nhớ, dựng system prompt), và system
prompt có thể lệch vài byte, làm mất prompt cache. Dùng lại thì system prompt giữ nguyên từng byte.

### Hai loại "ngăn kéo" trên đối tượng agent

```
┌──────────────── 🤖 AIAgent ─────────────────────────────┐
│ 📦 CẢ PHIÊN → GIỮ: session_id, model, client,           │
│    _cached_system_prompt, _session_db, _memory_manager, │
│    tools, _user_turn_count                              │
│ ─────────────────────────────────────────────────────── │
│ 📝 1 LƯỢT → XOÁ đầu mỗi lượt: _turn_author,             │
│    _last_compaction_in_place, _delivered_interim_texts, │
│    _incremental_persistence_failed, _fast_until, ...    │
└─────────────────────────────────────────────────────────┘
```

Python không tự phân biệt hai ngăn, nên lập trình viên phải tự "lau bảng".

### Quên reset thì sao

```
Lượt 1: BOT nhắn → agent._turn_author = "bot"
        (lượt kết thúc, agent vẫn trong cache)
Lượt 2: NGƯỜI nhắn
   ❌ không reset: vẫn = "bot" → đối xử với người như bot 🐛
   ✅ có reset:    = "người"
```

So sánh đời thường: bàn nhà hàng. Thông tin khách giữ suốt bữa; đĩa bẩn dọn sau mỗi món.

```
Prompt caching quan trọng
   ▼
Giữ 1 AIAgent sống qua nhiều lượt          ← "DÙNG LẠI"
   ▼
Đối tượng chứa cả trạng thái phiên lẫn trạng thái lượt
   ▼
Đầu mỗi lượt xoá trạng thái lượt            ← "RESET"
```

## 11. Prompt caching hoạt động thế nào

### Không có cache: đọc lại từ đầu

```
┌───────┬───────────────┬──────┬──────┬──────┬─────────┐
│ tools │ system prompt │ L1   │ L2   │ L3   │ tin mới │
└───────┴───────────────┴──────┴──────┴──────┴─────────┘
 ◄──────── model đọc lại toàn bộ mỗi request ──────────►
```

### Có cache: provider lưu phần đã đọc

```
Lượt 2: │ tools │ system │ L1 │ L2 │ tin │      ← đọc + LƯU
Lượt 3: │ tools │ system │ L1 │ L2 │ L3 │ tin │
         ◄── ✅ CACHE HIT ─────►◄ chỉ đọc phần mới ►
```

Với Anthropic, token đọc từ cache rẻ khoảng 1/10 giá thường; ghi cache đắt hơn một chút, trả một lần.

### Quy tắc: khớp tiền tố, từng byte, tính từ đầu

```
Lần trước: │ tools │ system "...28/10..." │ L1 │ L2 │
Lần này:   │ tools │ system "...29/10..." │ L1 │ L2 │ tin │
             ✅     ▲ lệch 1 ký tự
                    ◄──── ❌ mọi thứ phía sau bị đọc lại ────►

Đổi ở CUỐI │████████████████████████│░░│  mất ít
Đổi ở GIỮA │████████████│░░░░░░░░░░░░░░│  mất nửa
Đổi ở ĐẦU  │░░░░░░░░░░░░░░░░░░░░░░░░░░│  mất sạch
█ = từ cache (rẻ)   ░ = đọc lại (đắt)
```

### Theo thời gian

```
         tools+system   L1  L2  L3  L4
Lượt 1:  ░░░░░░░░░░░░   ░
Lượt 2:  ████████████   █   ░
Lượt 3:  ████████████   █   █   ░
Lượt 4:  ████████████   █   █   █   ░
```

Trong một lượt cũng vậy: mỗi vòng tool chỉ thêm đoạn cuối, nên gần như toàn bộ trúng cache.

### Hermes đặt mốc cache ở đâu (`agent/prompt_caching.py`)

Anthropic cho tối đa 4 mốc `cache_control`:

```
│ phần tĩnh system │ phần còn lại system │ L1 │ ... │ msg áp chót │ msg cuối │
                  📍1                   📍2                     📍3        📍4
```

📍1, 📍2 ở system prompt; 📍3, 📍4 trượt theo cuối hội thoại. TTL 5 phút hoặc 1 giờ; im lặng lâu
hơn thì cache hết hạn. Code gắn mốc: `apply_anthropic_cache_control` (`agent/prompt_caching.py:330`).

### Các quy tắc trong repo bảo vệ cache

| Quy tắc | Bảo vệ phần nào |
|---|---|
| System prompt tạo 1 lần/phiên | Phần đầu |
| Giữ agent sống qua nhiều lượt | System prompt + tools giống hệt |
| Slash command đổi prompt/tools → chờ phiên sau (`--now` để áp dụng ngay) | Không lệch prefix giữa chừng |
| `api_content` sidecar | Lịch sử gửi lại y hệt lần đầu |
| Không sửa message cũ | Phần giữa |
| Ngoại lệ: nén context | Chấp nhận mất cache một lần khi prompt quá dài |

Hình ảnh cần nhớ: **prompt là chồng gạch xây từ dưới lên**.

```
        ┌─────────┐  ← tin mới        (thêm: rẻ)
        ├─────────┤  ← lượt 3
        ├─────────┤  ← lượt 2
        ├─────────┤  ← lượt 1
        ├─────────┤  ← system prompt  (đổi: sập hết)
        └─────────┘  ← tools          (đổi: sập hết)
```
