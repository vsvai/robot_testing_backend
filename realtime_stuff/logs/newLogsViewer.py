import os
import re
from datetime import datetime, timedelta
import pytz  # pip install pytz
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
LOG_DIR = Path("/home/ubuntu/ota_stuff/logs")
MAC_PATTERN = re.compile(r"^[0-9A-F]{12}\.log$", re.IGNORECASE)
IST = pytz.timezone('Asia/Kolkata') # Set to Indian Standard Time

@app.get("/macs")
def list_available_macs():
    """Returns a list of all MAC IDs that have log files."""
    if not LOG_DIR.exists() or not LOG_DIR.is_dir():
        raise HTTPException(status_code=404, detail="Log directory not found.")
    
    mac_list = []
    
    # Iterate through the directory
    for file_path in LOG_DIR.iterdir():
        # Check if it's a file and matches the 12-character hex pattern
        if file_path.is_file() and MAC_PATTERN.match(file_path.name):
            # .stem extracts just the filename without the .log extension
            mac_list.append(file_path.stem)
            
    # Optional: Sort the list alphabetically for easier reading
    mac_list.sort()
            
    return {"total_logs": len(mac_list), "macs": mac_list}


@app.get("/view/{mac_id}")
def view_specific_log(
    mac_id: str, 
    hours: int = Query(None), 
    limit: int = Query(50)
):
    file_path = LOG_DIR / f"{mac_id}.log"
    
    if not file_path.exists():
        # Prevent null by returning a clear error JSON
        raise HTTPException(status_code=404, detail=f"Robot {mac_id} log not found.")

    def stream_logs():
        try:
            # Using encoding 'utf-8' and errors 'ignore' prevents binary crashes
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()

            if not all_lines:
                yield "Log file is currently empty.\n"
                return

            # Check if filter is out of range
            if hours is None or hours < 1 or hours > 168:
                yield f"--- [IST] Showing last {limit} entries (LATEST AT TOP) ---\n"
                # Slice last entries and show latest first
                for line in reversed(all_lines[-limit:]):
                    yield line
                return

            # Calculate IST cutoff
            cutoff_ist = datetime.now(IST) - timedelta(hours=hours)
            yield f"--- [IST] Logs since {cutoff_ist.strftime('%Y-%m-%d %H:%M:%S')} (LATEST AT TOP) ---\n"
            
            matching_lines = []
            # Iterate backwards to find newest logs faster
            for line in reversed(all_lines):
                try:
                    # Format: [2026-02-15 07:10:58] ADS value: 22.11
                    timestamp_str = line.split(" ")[0] + " " + line.split(" ")[1]
                    
                    # Fix: Added brackets to the strptime format to match the log string
                    log_time = datetime.strptime(timestamp_str, "[%Y-%m-%d %H:%M:%S]")
                    log_time = IST.localize(log_time) 
                    
                    if log_time >= cutoff_ist:
                        matching_lines.append(line)
                    
                    if len(matching_lines) >= limit:
                        break
                except (ValueError, IndexError):
                    continue 

            if not matching_lines:
                yield f"No logs found in the last {hours} hours in IST.\n"
            else:
                for line in matching_lines: # Already latest-first from the reversed loop
                    yield line

        except Exception as e:
            yield f"Server Error reading file: {str(e)}\n"

    # Actually return the generator wrapped in a StreamingResponse
    return StreamingResponse(stream_logs(), media_type="text/plain")

if __name__ == "__main__":
    import uvicorn
    # 0.0.0.0 makes it accessible across your network
    uvicorn.run(app, host="0.0.0.0", port=5174)
