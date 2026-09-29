from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import LLMOrchestrator
from app.agents.test_generation import (
    TestGenerationRequest,
    TestGenerationResponse,
)
from app.agents.test_generator import TestGenerationAgent
from app.context import (
    ContextAssembler,
    ContextQuery,
    HashEmbeddingProvider,
    PersistentContextRetriever,
)
from app.context.hybrid_retriever import HybridContextRetriever
from app.core.database import get_db
from app.agents.test_code_generation import (
    TestCodeGenerationRequest,
    TestCodeGenerationResponse,
)
from app.agents.test_code_generator import TestCodeGenerator
from app.agents.generated_file_service import GeneratedFileService

router = APIRouter(
    prefix="/tests",
    tags=["Test Generation"],
)


embedding_provider = HashEmbeddingProvider(
    dimension=128
)

persistent_retriever = PersistentContextRetriever(
    embedding_provider=embedding_provider
)

hybrid_retriever = HybridContextRetriever(
    vector_retriever=persistent_retriever
)

context_assembler = ContextAssembler()

orchestrator = LLMOrchestrator()

test_generator = TestGenerationAgent()

test_code_generator = TestCodeGenerator()

generated_file_service = GeneratedFileService()

@router.post(
    "/generate",
    response_model=TestGenerationResponse,
)
async def generate_tests(
    request: TestGenerationRequest,
    session: AsyncSession = Depends(get_db),
) -> TestGenerationResponse:

    try:
        context_query = ContextQuery(
            query=request.prompt,
            repository_path=request.repository_path,
            top_k=10,
        )

        retrieval_response = (
            await hybrid_retriever.retrieve(
                session=session,
                query=context_query,
            )
        )

        assembly = context_assembler.assemble(
            query=request.prompt,
            repository_path=request.repository_path,
            results=retrieval_response.results,
        )

        context_sections = []

        for chunk in assembly.chunks:
            header = (
                f"File: {chunk.relative_path}\n"
                f"Lines: {chunk.start_line}-{chunk.end_line}\n"
            )

            context_sections.append(
                header + chunk.content
            )

        context = "\n\n".join(
            context_sections
        )

        return await test_generator.generate(
            request=request,
            context=context,
            orchestrator=orchestrator,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc
@router.post(
    "/generate-code",
    response_model=TestCodeGenerationResponse,
)
async def generate_test_code(
    request: TestCodeGenerationRequest,
    session: AsyncSession = Depends(get_db),
) -> TestCodeGenerationResponse:

    try:
        context_query = ContextQuery(
            query=(
                "Generate executable tests for "
                + request.repository_path
            ),
            repository_path=request.repository_path,
            top_k=10,
        )

        retrieval_response = (
            await hybrid_retriever.retrieve(
                session=session,
                query=context_query,
            )
        )

        assembly = context_assembler.assemble(
            query=context_query.query,
            repository_path=request.repository_path,
            results=retrieval_response.results,
        )

        context_sections = []

        for chunk in assembly.chunks:
            header = (
                f"File: {chunk.relative_path}\n"
                f"Lines: {chunk.start_line}-{chunk.end_line}\n"
            )

            context_sections.append(
                header + chunk.content
            )

        context = "\n\n".join(
            context_sections
        )

        generated_response = (
            await test_code_generator.generate(
                request=request,
                test_cases=request.test_cases,
                context=context,
                orchestrator=orchestrator,
            )
        )

        for generated_file in generated_response.generated_files:
            generated_file_service.save(
                repository_path=request.repository_path,
                generated_file=generated_file,
            )

        return generated_response

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc