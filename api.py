"""
Simple viewer for the map tiles generated by query.py
Run with python3 api.py, then open http://localhost:8000 in your browser
"""

import fastapi, io
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse, Response, RedirectResponse
from PIL import Image
from query import Query

app = fastapi.FastAPI()
q = Query()

app.mount("/cache", StaticFiles(directory="cache"), name="cache")

@app.get("/")
async def index():
    return FileResponse('index.html')

@app.get("/tile/{z}/{x}/{y}.jpg")
async def tile(z: int, x: int, y: int):
    numpy_img = q.render_tile(x, y, z)
    if numpy_img is None:
        return Response(status_code=404)
    
    if type(numpy_img) == str:
        # redirect to cached file
        return RedirectResponse(url="/cache/" + numpy_img.split("/")[-1])
    
    img = Image.fromarray(numpy_img)

    img_io = io.BytesIO()
    img.save(img_io, "JPEG", quality=80)
    img_io.seek(0)

    return Response(img_io.read(), media_type="image/jpg")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)