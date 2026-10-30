import asyncio
import os
import re
import time
from dataclasses import dataclass


@dataclass
class ProcessResult:
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    error: str | None = None


class ProcessManager:
    SECRET_ENVIRONMENT_NAME = re.compile(
        r"(?:SECRET|TOKEN|PASSWORD|API[_-]?KEY|PRIVATE[_-]?KEY|CREDENTIAL)",
        re.IGNORECASE,
    )
    BEARER_SECRET = re.compile(
        r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]+"
    )
    NAMED_SECRET = re.compile(
        r"""(?ix)
        (\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|
        password|passwd|secret|client[_-]?secret|private[_-]?key)\b
        \s*[:=]\s*["']?)
        ([^\s,"'};]+)
        """
    )

    async def run(
        self,
        command: list[str],
        cwd: str,
        timeout_seconds: int,
        env: dict[str, str] | None = None,
    ) -> ProcessResult:

        start_time = time.perf_counter()

        if not command:
            return ProcessResult(
                exit_code=None,
                stdout="",
                stderr="",
                duration_seconds=0.0,
                error="Test runner command is empty.",
            )

        executable = command[0]

        if os.name == "nt":
            if executable in {"npx", "npm"}:
                executable = f"{executable}.cmd"

        process: asyncio.subprocess.Process | None = None
        process_environment = (
            {**os.environ, **env}
            if env is not None
            else dict(os.environ)
        )

        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                *command[1:],
                cwd=cwd,
                env=process_environment,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_seconds,
                )

            except asyncio.TimeoutError:
                process.kill()

                stdout, stderr = await process.communicate()

                duration = time.perf_counter() - start_time

                return ProcessResult(
                    exit_code=process.returncode,
                    stdout=self._redact_secrets(
                        stdout.decode("utf-8", errors="replace"),
                        process_environment,
                    ),
                    stderr=self._redact_secrets(
                        stderr.decode("utf-8", errors="replace"),
                        process_environment,
                    ),
                    duration_seconds=duration,
                    timed_out=True,
                    error=(
                        f"Process timed out after "
                        f"{timeout_seconds} seconds."
                    ),
                )

            duration = time.perf_counter() - start_time

            return ProcessResult(
                exit_code=process.returncode,
                stdout=self._redact_secrets(
                    stdout.decode("utf-8", errors="replace"),
                    process_environment,
                ),
                stderr=self._redact_secrets(
                    stderr.decode("utf-8", errors="replace"),
                    process_environment,
                ),
                duration_seconds=duration,
            )

        except FileNotFoundError:
            duration = time.perf_counter() - start_time

            return ProcessResult(
                exit_code=None,
                stdout="",
                stderr="",
                duration_seconds=duration,
                error="Test runner executable is unavailable.",
            )

        except OSError:
            duration = time.perf_counter() - start_time

            return ProcessResult(
                exit_code=None,
                stdout="",
                stderr="",
                duration_seconds=duration,
                error="Test runner could not be started.",
            )

    @classmethod
    def _redact_secrets(
        cls,
        output: str,
        environment: dict[str, str] | None,
    ) -> str:
        secret_values = {
            value for name, value in (environment or {}).items()
            if value and cls.SECRET_ENVIRONMENT_NAME.search(name)
        }
        for secret in sorted(secret_values, key=len, reverse=True):
            output = output.replace(secret, "[REDACTED]")
        output = cls.BEARER_SECRET.sub(r"\1[REDACTED]", output)
        return cls.NAMED_SECRET.sub(r"\1[REDACTED]", output)