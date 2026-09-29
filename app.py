import os
import uuid

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    send_from_directory
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

from config import Config
from database.db import get_connection
from ai.chatbot import get_ai_response
from pdf.extractor import extract_text_from_pdf


# ======================================
# FLASK APPLICATION
# ======================================

app = Flask(__name__)

app.config.from_object(Config)


# ======================================
# FILE UPLOAD SETTINGS
# ======================================

UPLOAD_FOLDER = "uploads"

ALLOWED_EXTENSIONS = {
    "pdf"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Maximum PDF size = 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# Create uploads folder
os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# ======================================
# HELPER FUNCTION
# ======================================

def allowed_file(filename):

    return (
        "." in filename
        and
        filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ======================================
# HOME PAGE
# ======================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# ======================================
# REGISTER
# ======================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form["name"].strip()

        email = request.form["email"].strip()

        password = request.form["password"]

        confirm_password = request.form.get(
            "confirmPassword",
            ""
        )

        # Check empty fields
        if not name or not email or not password:

            return "All fields are required."

        # Check password confirmation
        if password != confirm_password:

            return "Passwords do not match."

        # Hash password
        hashed_password = generate_password_hash(
            password
        )

        connection = None
        cursor = None

        try:

            connection = get_connection()

            cursor = connection.cursor()

            query = """
                INSERT INTO users
                (
                    name,
                    email,
                    password
                )
                VALUES
                (%s, %s, %s)
            """

            cursor.execute(
                query,
                (
                    name,
                    email,
                    hashed_password
                )
            )

            connection.commit()

            return redirect(
                url_for("login")
            )

        except Exception as e:

            print(
                "Registration error:",
                repr(e)
            )

            return (
                "Registration failed. "
                "Email may already exist."
            )

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template(
        "register.html"
    )


# ======================================
# LOGIN
# ======================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form["email"].strip()

        password = request.form["password"]

        connection = None
        cursor = None

        try:

            connection = get_connection()

            cursor = connection.cursor(
                dictionary=True
            )

            query = """
                SELECT
                    id,
                    name,
                    email,
                    password
                FROM users
                WHERE email = %s
            """

            cursor.execute(
                query,
                (email,)
            )

            user = cursor.fetchone()

            if user and check_password_hash(
                user["password"],
                password
            ):

                session["user_id"] = user["id"]

                session["user_name"] = user["name"]

                session["user_email"] = user["email"]

                return redirect(
                    url_for("dashboard")
                )

            return "Invalid email or password."

        except Exception as e:

            print(
                "Login error:",
                repr(e)
            )

            return (
                "Login failed. "
                "Please try again."
            )

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template(
        "login.html"
    )


# ======================================
# DASHBOARD
# ======================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        query = """
            SELECT
                id,
                filename,
                stored_filename,
                uploaded_at
            FROM documents
            WHERE user_id = %s
            ORDER BY uploaded_at DESC
        """

        cursor.execute(
            query,
            (session["user_id"],)
        )

        documents = cursor.fetchall()

        return render_template(
            "dashboard.html",
            name=session["user_name"],
            email=session["user_email"],
            documents=documents
        )

    except Exception as e:

        print(
            "Dashboard error:",
            repr(e)
        )

        return (
            "Unable to load dashboard."
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ======================================
# OPEN DOCUMENT DETAILS
# ======================================

@app.route(
    "/document/<int:document_id>"
)
def open_document(document_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        query = """
            SELECT
                id,
                filename,
                stored_filename,
                extracted_text,
                uploaded_at
            FROM documents
            WHERE id = %s
            AND user_id = %s
        """

        cursor.execute(
            query,
            (
                document_id,
                session["user_id"]
            )
        )

        document = cursor.fetchone()

        if not document:

            return (
                "Document not found."
            ), 404

        return render_template(
            "document.html",
            document=document
        )

    except Exception as e:

        print(
            "Open document error:",
            repr(e)
        )

        return (
            "Unable to open document."
        ), 500

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ======================================
# DELETE DOCUMENT
# ======================================

@app.route(
    "/delete-document/<int:document_id>",
    methods=["POST"]
)
def delete_document(document_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        # Find document belonging to user
        query = """
            SELECT
                stored_filename
            FROM documents
            WHERE id = %s
            AND user_id = %s
        """

        cursor.execute(
            query,
            (
                document_id,
                session["user_id"]
            )
        )

        document = cursor.fetchone()

        if not document:

            return (
                "Document not found."
            ), 404

        stored_filename = document[
            "stored_filename"
        ]

        # Delete database record
        delete_query = """
            DELETE FROM documents
            WHERE id = %s
            AND user_id = %s
        """

        cursor.execute(
            delete_query,
            (
                document_id,
                session["user_id"]
            )
        )

        connection.commit()

        # Delete physical PDF
        if stored_filename:

            file_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                stored_filename
            )

            if os.path.exists(file_path):

                os.remove(file_path)

        return redirect(
            url_for("pdf_assistant")
        )

    except Exception as e:

        if connection:

            connection.rollback()

        print(
            "Delete document error:",
            repr(e)
        )

        return (
            "Unable to delete document."
        ), 500

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ======================================
# VIEW ACTUAL PDF
# ======================================

@app.route(
    "/view-pdf/<int:document_id>"
)
def view_pdf(document_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        query = """
            SELECT
                stored_filename
            FROM documents
            WHERE id = %s
            AND user_id = %s
        """

        cursor.execute(
            query,
            (
                document_id,
                session["user_id"]
            )
        )

        document = cursor.fetchone()

        if not document:

            return (
                "Document not found."
            ), 404

        stored_filename = document[
            "stored_filename"
        ]

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            stored_filename
        )

        if not os.path.exists(file_path):

            return (
                "PDF file is missing from the server."
            ), 404

        return send_from_directory(
            app.config["UPLOAD_FOLDER"],
            stored_filename,
            as_attachment=False
        )

    except Exception as e:

        print(
            "View PDF error:",
            repr(e)
        )

        return (
            "Unable to open PDF."
        ), 500

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ======================================
# AI CHAT PAGE
# ======================================

@app.route("/chat")
def chat():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    return render_template(
        "chat.html"
    )


# ======================================
# AI CHAT API
# ======================================

@app.route(
    "/api/chat",
    methods=["POST"]
)
def api_chat():

    if "user_id" not in session:

        return jsonify({
            "error": "Please login first."
        }), 401

    data = request.get_json(
        silent=True
    ) or {}

    message = data.get(
        "message",
        ""
    ).strip()

    if not message:

        return jsonify({
            "error": "Message cannot be empty."
        }), 400

    try:

        answer = get_ai_response(
            message
        )

        connection = None
        cursor = None

        try:

            connection = get_connection()

            cursor = connection.cursor()

            query = """
                INSERT INTO chat_history
                (
                    user_id,
                    user_message,
                    ai_response
                )
                VALUES
                (%s, %s, %s)
            """

            cursor.execute(
                query,
                (
                    session["user_id"],
                    message,
                    answer
                )
            )

            connection.commit()

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

        return jsonify({
            "answer": answer
        })

    except Exception as e:

        print(
            "AI CHAT ERROR:",
            repr(e)
        )

        return jsonify({
            "error":
                "Unable to get an AI response. "
                "Please make sure Ollama is running."
        }), 500


# ======================================
# CHAT HISTORY
# ======================================

@app.route("/history")
def history():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        query = """
            SELECT
                id,
                user_message,
                ai_response,
                created_at
            FROM chat_history
            WHERE user_id = %s
            ORDER BY created_at DESC
        """

        cursor.execute(
            query,
            (session["user_id"],)
        )

        chats = cursor.fetchall()

        return render_template(
            "history.html",
            chats=chats
        )

    except Exception as e:

        print(
            "History error:",
            repr(e)
        )

        return (
            "Unable to load chat history."
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ======================================
# PDF ASSISTANT PAGE
# ======================================

@app.route("/pdf")
def pdf_assistant():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        # Get all PDFs uploaded
        # by the logged-in user
        query = """
            SELECT
                id,
                filename,
                stored_filename,
                uploaded_at
            FROM documents
            WHERE user_id = %s
            ORDER BY uploaded_at DESC
        """

        cursor.execute(
            query,
            (session["user_id"],)
        )

        documents = cursor.fetchall()

        return render_template(
            "pdf.html",
            documents=documents
        )

    except Exception as e:

        print(
            "PDF page error:",
            repr(e)
        )

        return (
            "Unable to load PDF documents."
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ======================================
# UPLOAD PDF
# ======================================

@app.route(
    "/upload-pdf",
    methods=["POST"]
)
def upload_pdf():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if "pdf" not in request.files:

        return "No PDF selected."

    file = request.files["pdf"]

    if file.filename == "":

        return "No PDF selected."

    if not allowed_file(
        file.filename
    ):

        return "Only PDF files are allowed."

    connection = None
    cursor = None

    file_path = None

    try:

        original_filename = secure_filename(
            file.filename
        )

        if not original_filename:

            return "Invalid filename."

        unique_name = (
            str(uuid.uuid4())
            + ".pdf"
        )

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            unique_name
        )

        # Save physical PDF
        file.save(
            file_path
        )

        # Extract text
        extracted_text = extract_text_from_pdf(
            file_path
        )

        if not extracted_text.strip():

            if os.path.exists(
                file_path
            ):

                os.remove(
                    file_path
                )

            return (
                "Could not extract text from this PDF. "
                "It may be a scanned/image-only PDF."
            )

        # Save document to database
        connection = get_connection()

        cursor = connection.cursor()

        query = """
            INSERT INTO documents
            (
                user_id,
                filename,
                stored_filename,
                extracted_text
            )
            VALUES
            (%s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (
                session["user_id"],
                original_filename,
                unique_name,
                extracted_text
            )
        )

        connection.commit()

        return redirect(
            url_for("pdf_assistant")
        )

    except Exception as e:

        print(
            "PDF upload error:",
            repr(e)
        )

        if file_path and os.path.exists(
            file_path
        ):

            os.remove(
                file_path
            )

        return (
            "PDF upload failed. "
            "Please try again."
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ======================================
# ASK QUESTION ABOUT PDF
# ======================================

@app.route(
    "/ask-pdf/<int:document_id>",
    methods=["POST"]
)
def ask_pdf(document_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    question = request.form.get(
        "question",
        ""
    ).strip()

    if not question:

        return "Question cannot be empty."

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        query = """
            SELECT
                id,
                filename,
                stored_filename,
                extracted_text,
                uploaded_at
            FROM documents
            WHERE id = %s
            AND user_id = %s
        """

        cursor.execute(
            query,
            (
                document_id,
                session["user_id"]
            )
        )

        document = cursor.fetchone()

        if not document:

            return (
                "Document not found."
            ), 404

        prompt = f"""
You are NexaAI, a PDF assistant.

Answer the user's question using ONLY
the information provided in the PDF.

If the answer is not available in the PDF,
say that the information was not found
in the document.

Do not invent information.

PDF CONTENT:

{document["extracted_text"]}

USER QUESTION:

{question}
"""

        answer = get_ai_response(
            prompt
        )

        return render_template(
            "document.html",
            document=document,
            answer=answer
        )

    except Exception as e:

        print(
            "PDF question error:",
            repr(e)
        )

        return (
            "Unable to answer the PDF question. "
            "Please try again."
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ======================================
# SUMMARIZE PDF
# ======================================

@app.route(
    "/summarize-pdf/<int:document_id>",
    methods=["POST"]
)
def summarize_pdf(document_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    connection = None
    cursor = None

    try:

        connection = get_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        query = """
            SELECT
                id,
                filename,
                stored_filename,
                extracted_text,
                uploaded_at
            FROM documents
            WHERE id = %s
            AND user_id = %s
        """

        cursor.execute(
            query,
            (
                document_id,
                session["user_id"]
            )
        )

        document = cursor.fetchone()

        if not document:

            return (
                "Document not found."
            ), 404

        pdf_text = document[
            "extracted_text"
        ]

        prompt = f"""
You are NexaAI, an AI document summarizer.

Summarize the following PDF content.

Rules:

1. Give a clear and easy-to-understand summary.
2. Include the main ideas.
3. Include important points.
4. Do not invent information.
5. Keep the summary reasonably short.
6. Use bullet points where useful.

PDF CONTENT:

{pdf_text}
"""

        summary = get_ai_response(
            prompt
        )

        return render_template(
            "document.html",
            document=document,
            summary=summary
        )

    except Exception as e:

        print(
            "PDF summary error:",
            repr(e)
        )

        return (
            "Unable to summarize the PDF. "
            "Please try again."
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ======================================
# LOGOUT
# ======================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ======================================
# ERROR HANDLERS
# ======================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "error.html",
        code=404,
        title="Page Not Found",
        message=(
            "Sorry, the page you are looking "
            "for does not exist."
        )
    ), 404


@app.errorhandler(
    RequestEntityTooLarge
)
def file_too_large(error):

    return render_template(
        "error.html",
        code=413,
        title="File Too Large",
        message=(
            "The PDF is too large. "
            "Please upload a PDF smaller than 10 MB."
        )
    ), 413


@app.errorhandler(500)
def internal_server_error(error):

    return render_template(
        "error.html",
        code=500,
        title="Something Went Wrong",
        message=(
            "An unexpected error occurred. "
            "Please try again later."
        )
    ), 500


# ======================================
# RUN APPLICATION
# ======================================

if __name__ == "__main__":

    app.run(
        debug=True
    )