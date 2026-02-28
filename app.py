import os
import json
import secrets
from pathlib import Path
import requests
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
import gradio as gr

# ----------------------
# Config
# ----------------------
FILES_JSON = "files.json"
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB
CATBOX_API = "https://catbox.moe/user/api.php"
SPACE_URL = "https://your-render-domain.com"  # Replace with your Render.com domain

# ----------------------
# Load saved files
# ----------------------
if os.path.exists(FILES_JSON):
    with open(FILES_JSON, "r") as f:
        files = json.load(f)
else:
    files = {}

def save_files():
    with open(FILES_JSON, "w") as f:
        json.dump(files, f, indent=2)

# ----------------------
# Upload function
# ----------------------
def upload_to_catbox(file, progress=gr.Progress()):
    filename = Path(file.name).name
    size = os.path.getsize(file.name)
    if size > MAX_FILE_SIZE:
        return "❌ File too large! Max 200 MB"

    # Simulate progress
    chunk_size = 1024 * 1024
    uploaded = 0
    with open(file.name, "rb") as f:
        while f.read(chunk_size):
            uploaded += chunk_size
            progress(min(uploaded / size,1.0))
        f.seek(0)

        # Upload to Catbox
        files_payload = {"fileToUpload": (filename,f)}
        data = {"reqtype":"fileupload"}
        r = requests.post(CATBOX_API, files=files_payload, data=data)

    catbox_url = r.text.strip()
    if not catbox_url.startswith("http"):
        return f"❌ Upload failed: {catbox_url}"

    # Generate fake ID
    fake_id = secrets.token_hex(6)
    random_filename = secrets.token_hex(5) + Path(filename).suffix

    files[fake_id] = {"original_name": filename,"random_name": random_filename,"url": catbox_url}
    save_files()

    # Fake link + copy button
    fake_link = f"{SPACE_URL}/download/{fake_id}"
    html = f"""
    <div style="display:flex;align-items:center;gap:10px;margin-top:5px;">
        <a href="{fake_link}" target="_blank">{filename}</a>
        <button onclick="navigator.clipboard.writeText('{fake_link}')"
            style="padding:4px 8px; background:#3b82f6;color:white;border:none;border-radius:5px;cursor:pointer;">
            Copy Link
        </button>
    </div>
    """
    return f"✅ Uploaded!{html}"

# ----------------------
# Gradio UI
# ----------------------
with gr.Blocks() as demo:
    gr.Markdown("## 🚀 Drag & Drop File to Upload (Max 200 MB)")

    with gr.Row():
        file_input = gr.File(label="Select or Drop File")
        progress_bar = gr.Progress()
        output_text = gr.HTML(label="Status / Download Link")

    upload_btn = gr.Button("Upload")
    upload_btn.click(upload_to_catbox, inputs=[file_input], outputs=[output_text], show_progress=True)

# ----------------------
# FastAPI app
# ----------------------
app = FastAPI()
app.mount("/", demo)  # Mount Gradio UI at root

# ----------------------
# Download route
# ----------------------
@app.get("/download/{fake_id}")
def download_file(fake_id: str):
    if fake_id not in files:
        return Response("File not found", status_code=404)

    catbox_url = files[fake_id]["url"]
    download_name = files[fake_id]["random_name"]

    r = requests.get(catbox_url, stream=True)
    def iterfile():
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={download_name}"}
    )

# ----------------------
# Launch (for local testing)
# ----------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
