"""Claude Code SDK provider — uses Max subscription via claude CLI.

Routes requests through the Claude Code SDK (async) with a subprocess CLI
fallback. Explicitly unsets ANTHROPIC_API_KEY to force subscription billing
rather than direct API usage.
"""

import asyncio
import concurrent.futures
import json
import os
import shutil
import subprocess
from typing import List, Optional

from .base import BaseProvider
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Attempt SDK import at module level; store availability flag.
_SDK_AVAILABLE = False
try:
    from claude_code_sdk import (
        query as _sdk_query,
        ClaudeCodeOptions,
        Message,
        AssistantMessage,
        ResultMessage,
        SystemMessage as _SystemMessage,
    )
    from claude_code_sdk._errors import MessageParseError as _MessageParseError

    # Monkey-patch the SDK message parser to handle unknown message types
    # (e.g. rate_limit_event) gracefully instead of raising an error that
    # terminates the entire stream.
    try:
        import claude_code_sdk._internal.message_parser as _mp
        import claude_code_sdk._internal.client as _client_mod

        _original_parse = _mp.parse_message

        def _tolerant_parse(data):
            try:
                return _original_parse(data)
            except _MessageParseError as exc:
                if "Unknown message type" in str(exc):
                    # Return a benign SystemMessage so the stream continues.
                    _mp.logger.debug("Skipping unknown message type: %s", data.get("type"))
                    return _SystemMessage(
                        subtype=data.get("type", "unknown"),
                        data=data,
                    )
                raise

        _mp.parse_message = _tolerant_parse
        # Also patch the reference in the client module that already imported it.
        if hasattr(_client_mod, "parse_message"):
            _client_mod.parse_message = _tolerant_parse
    except Exception:
        pass  # If patching fails, proceed with original behaviour.

    _SDK_AVAILABLE = True
except ImportError:
    _sdk_query = None
    ClaudeCodeOptions = None
    Message = None
    AssistantMessage = None
    ResultMessage = None
    _MessageParseError = None


class ClaudeCodeProvider(BaseProvider):
    """Claude provider that uses the Claude Code SDK / CLI with a Max subscription.

    Authentication flows through the ``claude`` CLI login, NOT through
    ANTHROPIC_API_KEY.  The provider actively removes that variable from the
    subprocess environment so that all usage is billed to the Max subscription.

    Two execution paths are supported, selected automatically:

    1. **SDK path** (preferred) -- uses ``claude-code-sdk`` async API with an
       ``asyncio.run()`` bridge.
    2. **CLI path** (fallback) -- shells out to ``claude -p --output-format json``.
    """

    name: str = "claude_code"

    # Default timeouts (seconds)
    TEXT_TIMEOUT: int = 300
    DOCUMENT_TIMEOUT: int = 1800

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        system_prompt: Optional[str] = None,
    ) -> None:
        self.model_name = model
        self.system_prompt = system_prompt

        # Determine which execution path is available.
        self._use_sdk = _SDK_AVAILABLE
        self._cli_available: Optional[bool] = None  # lazy-checked
        self._claude_bin: Optional[str] = None  # resolved by _check_cli_available

        if self._use_sdk:
            logger.info("ClaudeCodeProvider initialised with SDK path (claude-code-sdk)")
        else:
            logger.info("claude-code-sdk not installed; will use CLI fallback")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_cli_available(self) -> bool:
        """Return True if the ``claude`` binary is reachable."""
        if self._cli_available is None:
            self._claude_bin = shutil.which("claude")
            if self._claude_bin is None:
                # Search common install locations
                from pathlib import Path as _P
                _candidates = [
                    _P.home() / ".local" / "bin" / "claude",
                    _P("/opt/homebrew/bin/claude"),
                    _P("/usr/local/bin/claude"),
                    _P.home() / ".claude" / "bin" / "claude",
                ]
                for p in _candidates:
                    if p.exists() and os.access(p, os.X_OK):
                        self._claude_bin = str(p)
                        logger.info("Found claude CLI at %s", self._claude_bin)
                        break
            self._cli_available = self._claude_bin is not None
            if not self._cli_available:
                logger.warning("'claude' CLI not found on PATH or common locations")
        return self._cli_available

    @staticmethod
    def _clean_env() -> dict:
        """Return a copy of the environment with ANTHROPIC_API_KEY and CLAUDECODE removed."""
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("CLAUDECODE", None)
        return env

    # ------------------------------------------------------------------
    # SDK execution path
    # ------------------------------------------------------------------

    async def _query_sdk(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: int = TEXT_TIMEOUT,
    ) -> str:
        """Execute a single-turn query via the Claude Code SDK."""
        options = ClaudeCodeOptions(
            system_prompt=system_prompt or self.system_prompt or "",
            max_turns=1,
            model=self.model_name,
        )

        # Remove ANTHROPIC_API_KEY and CLAUDECODE for the duration of the call
        # so the SDK routes through the Max subscription and doesn't reject
        # nested session invocations.
        saved_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        saved_claudecode = os.environ.pop("CLAUDECODE", None)
        try:
            result_parts: list[str] = []
            final_result: Optional[str] = None
            # Wrap the async iteration to gracefully handle unknown message
            # types (e.g. rate_limit_event) that the SDK doesn't yet support.
            stream = _sdk_query(prompt=prompt, options=options).__aiter__()
            while True:
                try:
                    message = await stream.__anext__()
                except StopAsyncIteration:
                    break
                except Exception as iter_exc:
                    # If the SDK raises a MessageParseError for an unknown
                    # message type, log and skip it rather than aborting.
                    exc_name = type(iter_exc).__name__
                    if "MessageParseError" in exc_name or "Unknown message type" in str(iter_exc):
                        logger.debug("Skipping unrecognised SDK message: %s", iter_exc)
                        continue
                    raise
                # AssistantMessage has .content with text blocks
                if AssistantMessage is not None and isinstance(message, AssistantMessage):
                    for block in message.content:
                        if hasattr(block, "text"):
                            result_parts.append(block.text)
                # ResultMessage carries the final aggregated result
                elif ResultMessage is not None and isinstance(message, ResultMessage):
                    if message.result:
                        final_result = message.result
            # Prefer the ResultMessage.result if available; fall back to
            # concatenated AssistantMessage blocks.
            if final_result:
                return final_result
            return "".join(result_parts)
        finally:
            if saved_key is not None:
                os.environ["ANTHROPIC_API_KEY"] = saved_key
            if saved_claudecode is not None:
                os.environ["CLAUDECODE"] = saved_claudecode

    @staticmethod
    def _run_in_new_loop(coro, timeout: int) -> str:
        """Run a coroutine in a brand-new event loop (thread-safe).

        Creates a fresh loop, runs the coroutine, then closes the loop
        explicitly. This avoids anyio/asyncio cancel-scope conflicts that
        occur when ``asyncio.run()`` is used inside a thread pool while
        another loop is active in the parent thread.
        """
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                asyncio.wait_for(coro, timeout=timeout)
            )
        finally:
            # Shut down async generators and the loop itself.
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    def _run_sdk(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: int = TEXT_TIMEOUT,
    ) -> str:
        """Synchronous wrapper around the async SDK path.

        Handles being called from within an already-running event loop
        (e.g. the async pipeline runner) by spawning a dedicated thread
        with its own event loop.
        """

        # Check if we are inside a running event loop.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            # Already inside an async context — run the coroutine in a fresh
            # thread so it gets its own event loop (avoids cancel-scope errors).
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    self._run_in_new_loop,
                    self._query_sdk(prompt, system_prompt=system_prompt, timeout=timeout),
                    timeout,
                )
                return future.result(timeout=timeout)
        else:
            return self._run_in_new_loop(
                self._query_sdk(prompt, system_prompt=system_prompt, timeout=timeout),
                timeout,
            )

    # ------------------------------------------------------------------
    # CLI execution path (fallback)
    # ------------------------------------------------------------------

    def _run_cli(
        self,
        prompt: str,
        timeout: int = TEXT_TIMEOUT,
    ) -> str:
        """Execute a query by shelling out to the ``claude`` CLI."""
        if not self._check_cli_available():
            raise RuntimeError(
                "Neither claude-code-sdk nor the claude CLI is available. "
                "Install the SDK (pip install claude-code-sdk) or ensure "
                "'claude' is on your PATH."
            )

        cmd = [
            self._claude_bin or "claude",
            "-p",
            "--output-format", "json",
            "--model", self.model_name,
        ]

        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self._clean_env(),
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Claude CLI exited with code {result.returncode}: "
                f"{result.stderr[:500]}"
            )

        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Failed to parse Claude CLI JSON output: {exc}\n"
                f"Raw stdout (first 500 chars): {result.stdout[:500]}"
            ) from exc

        return response.get("result", "")

    # ------------------------------------------------------------------
    # Unified dispatch
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: int = TEXT_TIMEOUT,
    ) -> str:
        """Route to SDK or CLI, returning the model's text response."""
        if self._use_sdk:
            return self._run_sdk(prompt, system_prompt=system_prompt, timeout=timeout)
        return self._run_cli(prompt, timeout=timeout)

    # ------------------------------------------------------------------
    # BaseProvider interface
    # ------------------------------------------------------------------

    def generate_text(self, prompt: str) -> str:
        """Send a text-only prompt and return the response.

        Args:
            prompt: The text prompt to send.

        Returns:
            The model's text response.
        """
        try:
            return self._dispatch(prompt, timeout=self.TEXT_TIMEOUT)
        except Exception:
            logger.exception("ClaudeCodeProvider.generate_text failed")
            raise

    def generate_with_document(self, doc_path: str, prompt: str) -> str:
        """Extract text from a PDF document and send it with the prompt.

        Uses ``extract_financial_pages`` from the project's PDF utilities
        to pull the most relevant financial pages, then combines them with
        the user prompt for a single text query.

        Args:
            doc_path: Path to the PDF document.
            prompt: The instruction prompt.

        Returns:
            The model's text response.
        """
        try:
            from ..utils.pdf import extract_financial_pages
        except ImportError:
            logger.error(
                "Could not import extract_financial_pages from src.utils.pdf. "
                "Ensure pdfplumber is installed."
            )
            raise

        try:
            doc_text = extract_financial_pages(doc_path)
        except Exception:
            logger.exception("PDF text extraction failed for %s", doc_path)
            raise

        full_prompt = (
            f"DOCUMENT CONTENT:\n{doc_text}\n\n"
            f"INSTRUCTIONS:\n{prompt}"
        )

        try:
            return self._dispatch(
                full_prompt,
                system_prompt="You are a financial analyst. Analyse the document carefully.",
                timeout=self.DOCUMENT_TIMEOUT,
            )
        except Exception:
            logger.exception("ClaudeCodeProvider.generate_with_document failed")
            raise

    def generate_with_search(self, query: str, prompt: str) -> str:
        """Send a web-grounded generation request.

        The Claude Code SDK does not natively support search grounding, so
        the search query is prepended to the prompt as context.

        Args:
            query: The search query for grounding.
            prompt: The instruction prompt.

        Returns:
            The model's text response.
        """
        full_prompt = (
            f"Research the following topic and then answer:\n\n"
            f"Topic: {query}\n\n{prompt}"
        )
        try:
            return self._dispatch(full_prompt, timeout=self.TEXT_TIMEOUT)
        except Exception:
            logger.exception("ClaudeCodeProvider.generate_with_search failed")
            raise

    def health_check(self) -> bool:
        """Verify that the provider can execute a simple query.

        Returns:
            True if a trivial prompt completes successfully.
        """
        try:
            response = self._dispatch("Respond with exactly: OK", timeout=30)
            return len(response.strip()) > 0
        except Exception as e:
            logger.warning("ClaudeCodeProvider health check failed: %s", e)
            return False

    def list_models(self) -> List[str]:
        """Return the configured model name.

        Returns:
            Single-element list with the current model.
        """
        return [self.model_name]
