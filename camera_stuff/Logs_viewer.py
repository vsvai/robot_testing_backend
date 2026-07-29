import os
import re
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# --- CORS: Allow Browser Access ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
LOG_DIR = Path("/home/ubuntu/camera_stuff/logs") 
MAC_PATTERN = re.compile(r"^[0-9A-F]{12}\.log$", re.IGNORECASE)

@app.get("/macs")
def get_all_mac_ids():
    """Return a list of all MAC addresses that have log files."""
    if not LOG_DIR.exists():
        return {"mac_ids": [], "error": "Log directory not found"}
        
    files = [f.replace(".log", "") for f in os.listdir(LOG_DIR) if MAC_PATTERN.match(f)]
    return {"mac_ids": sorted(files)}

@app.get("/view/{mac_id}")
def view_specific_log(mac_id: str, limit: int = Query(50)):
    """
    Simplified Log Viewer:
    - Opens the log file.
    - Grabs the last 'limit' lines (default 50).
    - Returns them in REVERSE order (Newest log at the top).
    """
    file_path = LOG_DIR / f"{mac_id}.log"
    
    if not file_path.exists():
        return StreamingResponse(iter([f"Error: Log file for {mac_id} not found.\n"]), media_type="text/plain")

    def stream_logs():
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            if not lines:
                yield "Log file is empty.\n"
                return

            # 1. Slice the last 'limit' lines (e.g., last 50)
            last_lines = lines[-limit:]

            # 2. Reverse them so the Newest log is at the top of the screen
            for line in reversed(last_lines):
                yield line

        except Exception as e:
            yield f"Server Error reading file: {str(e)}\n"

    return StreamingResponse(stream_logs(), media_type="text/plain")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5176)
