import uvicorn
from config import HTTP_HOST, HTTP_PORT
from app.server import create_app

app = create_app()

if __name__ == "__main__":
    print(f"Starting Sudoyantra Backend on {HTTP_HOST}:{HTTP_PORT}")
    uvicorn.run(app, host=HTTP_HOST, port=HTTP_PORT)
