import asyncio
import os
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
    async def run(
        self,
        command: list[str],
        cwd: str,
        timeout_seconds: int,
    ) -> ProcessResult:
        start_time = time.perf_counter()
        process: asyncio.subprocess.Process | None = None

        executable = command[0]

        # Windows command shims such as npx.cmd and npm.cmd
        # are not resolved by create_subprocess_exec() when
        # only the bare command name is provided.
        if os.name == "nt":
            if executable in {"npx", "npm"}:
                executable = f"{executable}.cmd"

        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                *command[1:],
                cwd=cwd,
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
                    stdout=stdout.decode("utf-8", errors="replace"),
                    stderr=stderr.decode("utf-8", errors="replace"),
                    duration_seconds=duration,
                    timed_out=True,
                    error=f"Process timed out after {timeout_seconds} seconds.",
                )

            duration = time.perf_counter() - start_time

            return ProcessResult(
                exit_code=process.returncode,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                duration_seconds=duration,
            )

        except FileNotFoundError:
            duration = time.perf_counter() - start_time

            return ProcessResult(
                exit_code=None,
                stdout="",
                stderr="",
                duration_seconds=duration,
                error=f"Command not found: {command[0]}",
            )

        except OSError as exc:
            duration = time.perf_counter() - start_time

            return ProcessResult(
                exit_code=None,
                stdout="",
                stderr="",
                duration_seconds=duration,
                error=str(exc),
            )