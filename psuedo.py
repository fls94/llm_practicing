# tạo model AI instance
mục đích: bọc 1 lần gọi API tới LLM thành 1 hàm duy nhất.
    nhận vào : messages (list[dict]) + tools (list schema JSON)
    trả về   : 1 assistant message = {content: str | None, tool_calls: list[{id, name, arguments}]}
    giữ state: chỉ cấu hình kết nối, tạo 1 lần lúc khởi động
               (provider, model name, api_key, base_url, max_tokens, temperature)
    interface:
        class LLMClient:
            def __init__(self, model, api_key, base_url): ...
            def call(self, messages, tools) -> dict: ...
    tương ứng trong Hermes: AIAgent.__init__ (giữ client + model)
                            agent/turn_api_call.py: perform_api_call (1 lần gọi)

# tạo tools
mô tả tool 

# build input message
system prompt
user message

# main loop
messages = [{"role": "system", "content": SYSTEM_PROMPT},
              {"role": "user",   "content": user_input}]
while True:
      response = llm.call(messages, tools=TOOL_SCHEMAS)    # 1. gọi model
      messages.append(response)

      if not response.tool_calls:                           # 2. không gọi tool → xong
          return response.content

      for call in response.tool_calls:                      # 3. chạy từng tool
          result = TOOLS[call.name](**call.arguments)
          messages.append({"role": "tool", "tool_call_id": call.id,
                           "content": result})
      # 4. quay lại bước 1: model đọc kết quả tool và quyết định tiếp


