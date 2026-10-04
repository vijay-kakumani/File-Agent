from ollama import chat

response = chat(
    model = "qwen2.5:1.5b",
    messages = [
        {
            "role" : "user",
            "content" : "Explain agile in 3 sentences"
        }
    ]
)


print(response.message.content)