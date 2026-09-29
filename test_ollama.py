import ollama


response = ollama.chat(
    model="llama3.2",
    messages=[
        {
            "role": "user",
            "content": "Say hello to my college project."
        }
    ]
)


print(response["message"]["content"])