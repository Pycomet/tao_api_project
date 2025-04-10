from app.config import *
from app.routes import *

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@router.get("/")
async def root():
    return {"message": "Welcome to the TAO API Service"}

@router.get("/health")
async def health_check():
    return {"status": "healthy"}


app.include_router(router, prefix="/api/v1")
