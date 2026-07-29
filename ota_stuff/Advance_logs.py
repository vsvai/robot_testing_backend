import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pathlib import Path

app = FastAPI()

# Allow the dashboard (and any origin you need) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # or list specific origins, e.g. ["http://localhost:3000", "http://65.2.178.186:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
LOG_DIR = Path("/home/ubuntu/ota_stuff/logs") # Your log path

def get_mac_ids():
    return [f.replace(".log", "") for f in os.listdir(LOG_DIR) if f.endswith(".log")]

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    macs = get_mac_ids()
    # Simple HTML with dropdowns for MAC ID and Time
    mac_options = "".join([f'<option value="{m}">{m}</option>' for m in macs])
    return f"""
    <html>
        <body style="font-family: sans-serif; padding: 20px;">
            <h2>🤖 Sudoyantra Log Viewer</h2>
            <form action="/view" method="post">
                <label>Select Robot (MAC ID):</label><br>
                <select name="mac_id">{mac_options}</select><br><br>
                
                <label>Time Range:</label><br>
                <select name="time_range">
                    <option value="1">Last 1 Hour</option>
                    <option value="3">Last 3 Hours</option>
                    <option value="6">Last 6 Hours</option>
                    <option value="24">Yesterday / Last 24h</option>
                </select><br><br>

                <label>Max Lines:</label><br>
                <input type="number" name="limit" value="100"><br><br>
                
                <button type="submit">View Logs</button>
            </form>
        </body>
    </html>
    """

@app.post("/view", response_class=HTMLResponse)
async def view_logs(mac_id: str = Form(...), time_range: int = Form(...), limit: int = Form(...)):
    file_path = LOG_DIR / f"{mac_id}.log"
    if not file_path.exists():
        return "Log file not found."

    cutoff = datetime.now() - timedelta(hours=time_range)
    matching_lines = []

    with open(file_path, "r") as f:
        # We read from the end to get the most recent logs first
        for line in reversed(f.readlines()):
            try:
                # Adjust format "%Y-%m-%d %H:%M:%S" to match your actual log format
                log_time_str = line.split("]")[0].strip("[") 
                log_time = datetime.strptime(log_time_str, "%Y-%m-%d %H:%M:%S")
                
                if log_time >= cutoff:
                    matching_lines.append(line)
                if len(matching_lines) >= limit:
                    break
            except (ValueError, IndexError):
                continue

    content = "".join(matching_lines) if matching_lines else "No logs found for this period."
    return f"<h3>Logs for {mac_id} (Last {time_range}h)</h3><pre>{content}</pre><a href='/'>Back</a>"
