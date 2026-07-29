import os
import re
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# --- 1. ENABLE CORS (Fixes "Failed to fetch" in browser) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from ANY dashboard/IP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
# Ensure this path is correct for this specific server instance
LOG_DIR = Path("/home/ubuntu/ota_stuff/logs") 
MAC_PATTERN = re.compile(r"^[0-9A-F]{12}\.log$", re.IGNORECASE)

@app.get("/macs")
def get_all_mac_ids():
    """Return sorted list of MAC addresses found in the logs folder."""
    if not LOG_DIR.exists():
        return {"mac_ids": [], "error": f"Directory {LOG_DIR} not found"}
        
    files = [f.replace(".log", "") for f in os.listdir(LOG_DIR) if MAC_PATTERN.match(f)]
    return {"mac_ids": sorted(files)}

@app.get("/view/{mac_id}")
def view_specific_log(mac_id: str, limit: int = Query(50)):
    """
    Simple Viewer:
    - Opens the file.
    - Grabs the LAST 'limit' lines (default 50).
    - Returns them newest-first.
    """
    file_path = LOG_DIR / f"{mac_id}.log"
    
    if not file_path.exists():
        # Return a clean error string in the stream
        return StreamingResponse(
            iter([f"Error: Log file for {mac_id} not found.\n"]), 
            media_type="text/plain"
        )

    def stream_logs():
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            if not lines:
                yield "Log file is empty.\n"
                return

            # 1. Grab only the last N lines (No date parsing, just simple slicing)
            last_lines = lines[-limit:]

            # 2. Reverse them so the newest log is at the top of your dashboard
            for line in reversed(last_lines):
                yield line

        except Exception as e:
            yield f"Server Error: {str(e)}\n"

    # CRITICAL: Must return the StreamingResponse object
    return StreamingResponse(stream_logs(), media_type="text/plain")

if __name__ == "__main__":
    import uvicorn
    # Running on port 5173 as per your previous file
    uvicorn.run(app, host="0.0.0.0", port=5174)
