"""Z.ai SDK adapter (constitution II) — the official ``zai-sdk`` transport.

Selected with ``LLM_SDK=zai`` (default ``openai``). Z.ai's own SDK client
(:class:`zai.ZaiClient`) is NOT an ``openai.OpenAI`` subclass, but its chat
surface mirrors the OpenAI wire contract (``tools``, ``tool_choice``,
``response_format``, ``stream``) closely enough to sit underneath LangChain's
``ChatOpenAI`` machinery — proven empirically for the three consumer paths
this graph uses: plain ``invoke``, streaming (real-mode narration), and
tool-calling structured output.

Two compatibility facts this module encodes (both pinned by tests):

1. ``ChatOpenAI`` accepts a post-construction ``root_client`` swap to a
   ``ZaiClient`` — invoke/stream then run through the official SDK's HTTP
   stack (retries, error shaping) instead of the generic shim.
2. LangChain's ``with_structured_output`` DEFAULT method (json_schema) needs
   ``chat.completions.with_raw_response.parse`` / the beta parse helper,
   which the Z.ai SDK does not implement. The SDK DOES support native tool
   calling, so :class:`ChatZai` pins ``method="function_calling"`` — the D8
   wrapper's validate/retry semantics are unchanged on top of it.
"""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI
from zai import ZaiClient

__all__ = ["ChatZai", "build_chat_zai"]


class ChatZai(ChatOpenAI):
    """``ChatOpenAI`` transported by the official Z.ai SDK client.

    The only override is the structured-output method pin (see module
    docstring); invoke/stream/labels are inherited untouched, so every
    consumer in the graph (``call_structured``, the D8 retry wrapper, the
    real-mode narration stream) keeps its exact behavior.
    """

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        """Pin the function-calling method: the Z.ai SDK implements native
        tool calling but not the json_schema parse helpers LangChain's
        default method requires."""
        kwargs.setdefault("method", "function_calling")
        return super().with_structured_output(schema, **kwargs)


def build_chat_zai(
    *,
    model: str,
    api_key: str,
    base_url: str,
    timeout: float = 120.0,
) -> ChatZai:
    """Build the transport-swapped client for one settings tuple.

    ``base_url`` travels on BOTH objects: the LangChain layer reads it for
    metadata, and the ``ZaiClient`` actually dials it. Fails at the first
    real call (never silently) when the key is wrong — the SDK surfaces
    Z.ai's typed 401 as-is.
    """
    llm = ChatZai(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0,  # literal 0 — determinism, constitution III
        timeout=timeout,
    )
    llm.root_client = ZaiClient(api_key=api_key, base_url=base_url, timeout=timeout)
    return llm
