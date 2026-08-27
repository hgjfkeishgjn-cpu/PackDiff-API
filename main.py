import difflib
import io
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pypdf import PdfReader
from pydantic import BaseModel

app = FastAPI(
    title="PackDiff API",
    description="Extract text from two PDF files and calculate a structured line-by-line text diff.",
    version="1.0.0",
)

class DiffSummary(BaseModel):
    total_changes: int
    additions: int
    deletions: int
    modifications: int

class DiffResponse(BaseModel):
    summary: DiffSummary
    diff_lines: list[str]

def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    """Extracts plain text from raw PDF bytes using PyPDF."""
    try:
        pdf_file = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_file)
        text_pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(text_pages)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse PDF file: {str(e)}",
        )

@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "PackDiff Engine"}

@app.post(
    "/api/v1/diff",
    response_model=DiffResponse,
    tags=["Comparison"],
    summary="Compare two PDF documents",
)
async def diff_pdfs(
    original_file: UploadFile = File(..., description="Original PDF document"),
    modified_file: UploadFile = File(..., description="Modified PDF document"),
):
    """
    Upload two PDF files (`original_file` and `modified_file`) to retrieve 
    a structured diff report and delta metrics.
    """
    # 1. Validate File Types
    for f in [original_file, modified_file]:
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{f.filename}' is not a valid PDF.",
            )

    # 2. Extract Text
    original_bytes = await original_file.read()
    modified_bytes = await modified_file.read()

    text_orig = extract_text_from_pdf_bytes(original_bytes)
    text_mod = extract_text_from_pdf_bytes(modified_bytes)

    lines_orig = text_orig.splitlines()
    lines_mod = text_mod.splitlines()

    # 3. Perform Unified Diff Analysis
    diff_gen = list(
        difflib.unified_diff(
            lines_orig,
            lines_mod,
            fromfile="original.pdf",
            tofile="modified.pdf",
            lineterm="",
        )
    )

    # 4. Compute Statistics
    additions = sum(1 for line in diff_gen if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in diff_gen if line.startswith("-") and not line.startswith("---"))
    
    # Calculate simple stats
    summary = DiffSummary(
        total_changes=additions + deletions,
        additions=additions,
        deletions=deletions,
        modifications=min(additions, deletions),
    )

    return DiffResponse(summary=summary, diff_lines=diff_gen)
