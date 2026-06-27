from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

# ── User ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class UserInDB(BaseModel):
    id: str
    email: str
    full_name: str
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

# ── Document ─────────────────────────────────────────────────────────────────

class DocumentMetadata(BaseModel):
    id: str
    filename: str
    file_type: str
    size_bytes: int
    chunk_count: int
    uploaded_by: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "processing"  # processing | ready | error
    error: Optional[str] = None

class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    size_bytes: int
    chunk_count: int
    uploaded_at: datetime
    status: str
    error: Optional[str] = None  # populated when status == "error"

# ── Chat ─────────────────────────────────────────────────────────────────────

class Citation(BaseModel):
    filename: str
    page_number: Optional[int]
    chunk_id: str

class ChatMessage(BaseModel):
    role: str  # user | assistant
    content: str
    citations: List[Citation] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ChatSession(BaseModel):
    id: str
    user_id: str
    title: str
    messages: List[ChatMessage] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    session_id: str
    answer: str
    citations: List[Citation]
    agent_trace: List[str]

# ── Chunk ────────────────────────────────────────────────────────────────────

class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    text: str
    page_number: Optional[int]
    chunk_index: int