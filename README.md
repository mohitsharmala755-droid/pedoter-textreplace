Pedoter Skills — PDF Text Replace Service
A separate Python service (not part of your main Node backend) that does exact
find-and-replace on PDF text, matching the original font/size/color/position.
Why a separate service
Your main backend is Node/Express. This feature needs PyMuPDF, a Python
library — there's no equivalent JS library with this capability. So this runs
as its own small service, called by your frontend directly (or you can proxy
it through your Node backend later if you want one unified API).
Deploy to Render (same process as your Node backend)
Push this folder (`main.py`, `requirements.txt`) to a new GitHub repo,
e.g. `pedoter-textreplace`.
Render dashboard → New + → Web Service → connect that repo.
Settings:
Runtime: Python 3
Build command: `pip install -r requirements.txt`
Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
Deploy. Render gives you a URL like `https://pedoter-textreplace.onrender.com`.
Test it's alive: visit `https://pedoter-textreplace.onrender.com/health`
→ should show `{"status":"ok"}`.
API
`POST /replace`
`file`: the PDF (multipart form-data)
`replacements`: JSON string, e.g. `[{"find":"John Smith","replace":"Jane Doe"}]`
`case_sensitive`: `true`/`false` (optional, default false)
Returns the modified PDF as a file download. If nothing matched, returns a
404 with an error message (so your frontend can tell the user nothing was
found, rather than silently returning the unchanged file).
Before going further
Once deployed, test it directly with a real PDF and a simple find/replace
before relying on the frontend integration — that's the real test I couldn't
run myself from here. If a specific case breaks (a custom font, a very long
replacement, non-Latin text), send me the PDF and the exact find/replace you
tried, and I'll fix the actual behavior instead of guessing.
