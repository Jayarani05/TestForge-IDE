import logging
from pathlib import Path

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
    SaveGeneratedTestCodeRequest,
    SaveGeneratedTestCodeResponse,
    TestCodeGenerationRequest,
    TestCodeGenerationResponse,
)
from app.agents.test_code_generator import TestCodeGenerator
from app.agents.generated_file_service import GeneratedFileService
from app.agents.code_validator import (
    GeneratedCodeValidationError,
    GeneratedCodeValidator,
)
from app.repository.analyzer_service import RepositoryAnalyzerService

router = APIRouter(
    prefix="/tests",
    tags=["Test Generation"],
)

logger = logging.getLogger(__name__)

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

generated_code_validator = GeneratedCodeValidator()

repository_analyzer = RepositoryAnalyzerService()

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
        analysis = repository_analyzer.analyze_repository(
            request.repository_path
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="The selected repository could not be found.",
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail="Permission denied while analyzing the selected repository.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    if not analysis.supported_test_languages:
        raise HTTPException(
            status_code=422,
            detail=(
                "No supported Python, JavaScript, or TypeScript project "
                "language was detected."
            ),
        )

    language_names = {
        "python": "Python",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
    }
    if language_names[request.language.value] not in analysis.supported_test_languages:
        raise HTTPException(
            status_code=422,
            detail=(
                f"The selected repository does not provide evidence for "
                f"{request.language.value}."
            ),
        )

    if request.framework.value not in analysis.supported_test_frameworks:
        raise HTTPException(
            status_code=422,
            detail=(
                f"No repository evidence supports {request.framework.value}. "
                "Choose a detected framework or add its dependency/configuration "
                "and analyze the repository again."
            ),
        )

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
        return generated_response

    except GeneratedCodeValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception("Test-code generation failed.")
        raise HTTPException(
            status_code=502,
            detail="Test-code generation failed. Review the request and retry.",
        ) from exc


@router.post(
    "/save-code",
    response_model=SaveGeneratedTestCodeResponse,
)
async def save_generated_test_code(
    request: SaveGeneratedTestCodeRequest,
) -> SaveGeneratedTestCodeResponse:
    validation = generated_code_validator.validate(
        code=request.generated_file.code,
        language=request.generated_file.language.value,
        framework=request.generated_file.framework.value,
    )
    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail=f"Generated code validation failed: {validation.error}",
        )

    try:
        saved_path = generated_file_service.save(
            repository_path=request.repository_path,
            generated_file=request.generated_file,
            overwrite=request.overwrite,
        )
    except FileExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "A file already exists at the generated destination. "
                "Confirm replacement before retrying."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except OSError as exc:
        logger.exception("Generated test file could not be saved.")
        raise HTTPException(
            status_code=500,
            detail="Generated test file could not be saved.",
        ) from exc

    return SaveGeneratedTestCodeResponse(
        repository_path=str(Path(request.repository_path).resolve()),
        file_path=saved_path,
        relative_path=request.generated_file.file_path,
        code=request.generated_file.code,
    )