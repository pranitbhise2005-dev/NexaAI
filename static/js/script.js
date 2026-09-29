const sendButton =
    document.getElementById("sendButton");

const messageInput =
    document.getElementById("messageInput");

const messages =
    document.getElementById("messages");

const typingIndicator =
    document.getElementById("typingIndicator");


/* ======================================
   ADD MESSAGE
====================================== */

function addMessage(text, sender) {

    const row =
        document.createElement("div");

    row.classList.add(
        "message-row"
    );


    if (sender === "user") {

        row.classList.add(
            "user-row"
        );

        row.innerHTML = `
            <div class="message user-message">
                <div class="message-name">
                    You
                </div>
                <p>${escapeHtml(text)}</p>
            </div>
        `;

    } else {

        row.classList.add(
            "assistant-row"
        );

        row.innerHTML = `
            <div class="message-avatar">
                🤖
            </div>

            <div class="message assistant-message">

                <div class="message-name">
                    NexaAI
                </div>

                <p>${escapeHtml(text)}</p>

            </div>
        `;

    }


    messages.appendChild(row);

    messages.scrollTop =
        messages.scrollHeight;
}


/* ======================================
   ESCAPE HTML
====================================== */

function escapeHtml(text) {

    const div =
        document.createElement("div");

    div.textContent = text;

    return div.innerHTML;
}


/* ======================================
   SHOW TYPING
====================================== */

function showTyping() {

    if (typingIndicator) {

        typingIndicator.style.display =
            "flex";

        messages.scrollTop =
            messages.scrollHeight;

    }

}


/* ======================================
   HIDE TYPING
====================================== */

function hideTyping() {

    if (typingIndicator) {

        typingIndicator.style.display =
            "none";

    }

}


/* ======================================
   SEND MESSAGE
====================================== */

async function sendMessage() {

    const message =
        messageInput.value.trim();


    if (!message) {
        return;
    }


    addMessage(
        message,
        "user"
    );


    messageInput.value = "";


    sendButton.disabled = true;

    showTyping();


    try {

        const response =
            await fetch(
                "/api/chat",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        message: message
                    })
                }
            );


        const data =
            await response.json();


        hideTyping();


        if (data.answer) {

            addMessage(
                data.answer,
                "assistant"
            );

        } else if (data.error) {

            addMessage(
                "NexaAI Error: " +
                data.error,
                "assistant"
            );

        } else {

            addMessage(
                "NexaAI could not generate a response.",
                "assistant"
            );

        }

    } catch (error) {

        hideTyping();

        addMessage(
            "Unable to connect to NexaAI. Please check that the Flask server and Ollama are running.",
            "assistant"
        );

        console.error(error);

    }


    sendButton.disabled = false;

    messageInput.focus();
}


/* ======================================
   SEND BUTTON
====================================== */

if (sendButton) {

    sendButton.addEventListener(
        "click",
        sendMessage
    );

}


/* ======================================
   ENTER KEY
====================================== */

if (messageInput) {

    messageInput.addEventListener(
        "keydown",
        function(event) {

            if (
                event.key === "Enter" &&
                !event.shiftKey
            ) {

                event.preventDefault();

                sendMessage();

            }

        }
    );

}