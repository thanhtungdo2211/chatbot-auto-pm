"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from auto_pm_agent_api.infrastructure.api.models import (
    ChatRequest,
    ChatResponse,
    WorkReportExtractRequest,
    WorkReportExtractResponse,
)
from auto_pm_agent_api.infrastructure.api.dependencies import (
    get_chat_service,
    get_work_report_extractor,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log", encoding="utf-8")
    ]
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Awesome Agent API",
    description="AI-powered project management chatbot with multi-session support",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Health check endpoint."""
    return {"message": "Awesome Agent API is running 🚀", "version": "0.1.0"}


@app.get("/health")
def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "service": "awesome-agent-api",
        "version": "0.1.0"
    }


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint for handling user queries.
    
    Args:
        request: ChatRequest containing user_id, query, file_content, etc.
        
    Returns:
        ChatResponse with the bot's response
    """
    try:
        logger.info(f"Received chat request from user {request.user_id}")
        
        # Get chat service instance
        chat_service = get_chat_service()
        
        # Handle the query
        response_text, mode_report = chat_service.handle_query(
            user_id=request.user_id,
            role=request.role,
            query=request.query,
            file_content=request.file_content,
            mode_report=request.mode_report,
        )
        
        return ChatResponse(
            user_id=request.user_id,
            query=request.query,
            response=response_text,
            success=True,
            mode_report=mode_report,
        )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        return ChatResponse(
            user_id=request.user_id,
            query=request.query,
            response="Xin lỗi, đã xảy ra lỗi khi xử lý yêu cầu của bạn.",
            success=False,
            error=str(e),
            mode_report=request.mode_report,
        )


@app.post("/reports/extract", response_model=WorkReportExtractResponse)
def extract_work_report(request: WorkReportExtractRequest):
    """
    Extract work report content into structured JSON.
    """
    try:
        logger.info("Received work report extraction request")
        extractor = get_work_report_extractor()
        data = extractor.extract(request.content)
        return WorkReportExtractResponse(
            success=True,
            data=data,
            message="Trích xuất báo cáo thành công"
        )
    except ValueError as e:
        logger.warning("Invalid work report payload: %s", e)
        return WorkReportExtractResponse(
            success=False,
            data=None,
            message="Nội dung không đúng yêu cầu",
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Error extracting work report: {e}", exc_info=True)
        return WorkReportExtractResponse(
            success=False,
            data=None,
            message="Không thể trích xuất báo cáo",
            error=str(e)
        )


@app.post("/memory/clear")
def clear_memory(user_id: int):
    """
    Clear conversation memory for a specific user.
    
    Args:
        user_id: User identifier
        
    Returns:
        Success message
    """
    try:
        chat_service = get_chat_service()
        chat_service.memory.clear_history(user_id)
        
        return {
            "success": True,
            "message": f"Đã xóa lịch sử hội thoại của user {user_id}"
        }
        
    except Exception as e:
        logger.error(f"Error clearing memory: {e}")
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
