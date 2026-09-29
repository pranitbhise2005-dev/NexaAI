import ollama


def get_ai_response(message):

    response = ollama.chat(
        model="llama3.2",
        messages=[
            {
                "role": "user",
                "content": message
            }
        ]
    )

    return response["message"]["content"]