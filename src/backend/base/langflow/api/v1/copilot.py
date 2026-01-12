"""API endpoints for Copilot Agent workflow generation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from lfx.log.logger import logger
from pydantic import BaseModel, Field
from sqlmodel import select

from langflow.agent_workflow.copilot import format_workflow_json, generate_workflow_with_llm, validate_workflow_json
from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder

router = APIRouter(prefix="/copilot", tags=["Copilot"])


class CopilotMessage(BaseModel):
    """Message in copilot conversation."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class CopilotChatRequest(BaseModel):
    """Request for copilot chat."""

    message: str = Field(..., description="User message")
    conversation_history: list[CopilotMessage] | None = Field(
        default=None, description="Previous conversation messages"
    )


class CopilotChatResponse(BaseModel):
    """Response from copilot chat."""

    message: str = Field(..., description="Assistant response message")
    workflow_data: dict | None = Field(default=None, description="Generated workflow JSON if workflow was created")
    flow_id: str | None = Field(default=None, description="Created flow ID if workflow was saved")


class CopilotGenerateWorkflowRequest(BaseModel):
    """Request to generate and save workflow."""

    workflow_data: dict = Field(..., description="Workflow JSON data")
    flow_name: str = Field(..., description="Name for the new flow")
    description: str | None = Field(default=None, description="Flow description")


@router.post("/chat", response_model=CopilotChatResponse, status_code=200)
async def copilot_chat(
    *,
    request: CopilotChatRequest,
    current_user: CurrentActiveUser,
) -> CopilotChatResponse:
    """Chat with copilot agent to generate workflows.

    Args:
        request: Chat request with message and conversation history
        current_user: Current authenticated user

    Returns:
        Copilot response with message and optionally generated workflow
    """
    try:
        await logger.adebug(f"Received copilot chat request: message length={len(request.message)}")
        # Convert conversation history format
        history = None
        if request.conversation_history:
            history = [{"role": msg.role, "content": msg.content} for msg in request.conversation_history]
            await logger.adebug(f"Conversation history: {len(history)} messages")

        # Generate workflow using LLM
        await logger.ainfo("Starting workflow generation...")
        workflow_data = await generate_workflow_with_llm(
            user_message=request.message,
            conversation_history=history,
        )
        await logger.ainfo("Workflow generation completed successfully")

        # Create response message
        response_message = (
            "I've generated a workflow based on your requirements. "
            "The workflow has been created and is ready to use. "
            "You can now view and run it in the flow editor."
        )

        return CopilotChatResponse(
            message=response_message,
            workflow_data=workflow_data,
        )

    except ValueError as e:
        # Return error message but don't fail the request
        await logger.awarning(f"Copilot chat ValueError: {e}")
        return CopilotChatResponse(
            message=f"I encountered an error: {e!s}. Please try rephrasing your request.",
            workflow_data=None,
        )
    except Exception as e:
        await logger.aerror(f"Error in copilot chat11: {e}")
        await logger.aexception("Error in copilot chat")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating workflow: {e!s}"
        ) from e


@router.post("/generate-workflow", response_model=dict, status_code=201)
async def generate_and_save_workflow(
    *,
    request: CopilotGenerateWorkflowRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> dict:
    """Generate workflow from user message and save to database.

    Args:
        request: Request with user message and flow metadata
        session: Database session
        current_user: Current authenticated user

    Returns:
        Created flow data
    """
    try:
        # Validate workflow data
        is_valid, error_msg = validate_workflow_json(request.workflow_data)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid workflow structure: {error_msg}"
            )

        # Format workflow
        workflow_data = format_workflow_json(request.workflow_data)

        # Get default folder
        default_folder = (
            await session.exec(
                select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME, Folder.user_id == current_user.id)
            )
        ).first()
        # import pdb; pdb.set_trace()

        if not default_folder:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Default folder not found")

        # Create flow
        # TODO 这里的数据验证出错：Value error, Flow must have nodes
        flow_create = FlowCreate(
            name=request.flow_name,
            description=request.description,
            data=workflow_data["data"],
            user_id=current_user.id,
            folder_id=default_folder.id,
            is_component=False,
        )

        db_flow = Flow.model_validate(flow_create, from_attributes=True)
        session.add(db_flow)
        await session.commit()
        await session.refresh(db_flow)

        return {
            "id": str(db_flow.id),
            "name": db_flow.name,
            "data": db_flow.data,
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error saving workflow: {e!s}"
        await logger.aexception(error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error saving workflow: {e!s}"
        ) from e
