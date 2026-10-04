from pathlib import Path
from typing import Dict, Any, Optional, Union

from app.agent.intent_parser import (
    IntentParser,
    ParsedRequest,
    IntentType,
    TargetType,
    FollowUpAction,
)
from app.agent.target_resolver import TargetResolver, target_resolver
from app.models import AgentResult, DocumentInfo
from app.rag import DocumentQAService, DocumentSummarizer
from app.services import (
    state_service,
    document_service,
    search_service,
    indexing_service,
)


class DocumentAgentService:
    """
    Phase V2.2 Application-Level Canonical Orchestration Service.
    Coordinates query understanding, target resolution, candidate search, active document
    state management, RAG Q&A, map-reduce summarization, and native Win32 document operations.
    """

    def __init__(
        self,
        parser: Optional[IntentParser] = None,
        qa_service: Optional[DocumentQAService] = None,
        summarizer: Optional[DocumentSummarizer] = None,
        target_resolver_inst: Optional[TargetResolver] = None,
    ):
        self.parser = parser or IntentParser()
        self.qa_service = qa_service or DocumentQAService()
        self.summarizer = summarizer or DocumentSummarizer()
        self.target_resolver = target_resolver_inst or target_resolver

    def process_message(self, user_message: str) -> Union[AgentResult, Dict[str, Any], str]:
        parsed = self.parser.parse(user_message)
        result = self.execute_request(parsed)
        return result

    def process_message_stream(self, user_message: str):
        """
        Streaming generator for natural language queries.
        Streams LLM tokens incrementally for ASK and SUMMARIZE.
        Yields fast structured responses for FIND, LOCATION, OPEN, REFRESH.
        """
        parsed = self.parser.parse(user_message)
        current_doc = state_service.active_document_path

        # 1. ASK INTENT
        if parsed.intent == IntentType.ASK:
            target_doc_path = current_doc
            if parsed.target == TargetType.DOCUMENT_REFERENCE and parsed.document_reference:
                res = self.target_resolver.resolve_reference(parsed.document_reference)
                if res.resolved_path and res.resolved_path.exists():
                    target_doc_path = res.resolved_path
                    state_service.set_active_document(target_doc_path)

            if target_doc_path is None:
                err_msg = "No active document selected. Please select or find a document first."
                yield {
                    "type": "meta",
                    "action": "ask",
                    "intent": "ASK",
                    "current_document": state_service.get_active_document_info(),
                    "results": [],
                    "success": False,
                }
                yield {"type": "token", "content": err_msg}
                yield {"type": "done", "message": err_msg}
                return

            question = parsed.question or parsed.raw_message
            yield {
                "type": "meta",
                "action": "ask",
                "intent": "ASK",
                "current_document": state_service.get_active_document_info(),
                "results": [],
                "success": True,
            }
            final_res = None
            for ev in self.qa_service.ask_stream(question=question, document_path=target_doc_path):
                if ev.get("type") == "token":
                    yield ev
                elif ev.get("type") == "done":
                    final_res = ev.get("result")

            ans = final_res.answer if final_res else ""
            yield {
                "type": "done",
                "action": "ask",
                "message": ans,
                "current_document": state_service.get_active_document_info(),
                "success": final_res.grounded if final_res else False,
            }
            return

        # 2. SUMMARIZE INTENT
        if parsed.intent == IntentType.SUMMARIZE:
            target_path = current_doc
            if parsed.target != TargetType.CURRENT_DOCUMENT and parsed.query:
                search_res = search_service.search_candidates(
                    query=parsed.query,
                    extension_filter=parsed.extension_filter,
                    folder_constraint=parsed.folder_constraint,
                    date_constraint=parsed.date_constraint,
                )
                if not search_res.top_candidate:
                    err_msg = "No matching document found to summarize."
                    yield {
                        "type": "meta",
                        "action": "summarize",
                        "intent": "SUMMARIZE",
                        "current_document": state_service.get_active_document_info(),
                        "results": [],
                        "success": False,
                    }
                    yield {"type": "token", "content": err_msg}
                    yield {"type": "done", "message": err_msg}
                    return
                target_path = Path(search_res.top_candidate.path)
                state_service.set_active_document(target_path)

            if target_path is None:
                err_msg = "No active document selected. Please select or find a document first."
                yield {
                    "type": "meta",
                    "action": "summarize",
                    "intent": "SUMMARIZE",
                    "current_document": state_service.get_active_document_info(),
                    "results": [],
                    "success": False,
                }
                yield {"type": "token", "content": err_msg}
                yield {"type": "done", "message": err_msg}
                return

            yield {
                "type": "meta",
                "action": "summarize",
                "intent": "SUMMARIZE",
                "current_document": state_service.get_active_document_info(),
                "results": [],
                "success": True,
            }
            final_res = None
            for ev in self.summarizer.summarize_file_stream(target_path):
                if ev.get("type") == "token":
                    yield ev
                elif ev.get("type") == "done":
                    final_res = ev.get("result")

            summary_text = final_res.summary if final_res else ""
            yield {
                "type": "done",
                "action": "summarize",
                "message": summary_text,
                "current_document": state_service.get_active_document_info(),
                "success": (final_res.error is None) if final_res else False,
            }
            return

        # 3. All other intents (FIND, LOCATION, OPEN, READ, REFRESH)
        result = self.execute_request(parsed)
        action_str = "unknown"
        intent_str = getattr(result, "intent", "UNKNOWN")
        user_lower = user_message.lower()
        if intent_str == "FIND":
            action_str = "search_open" if "open" in user_lower else "search"
        elif intent_str == "OPEN":
            action_str = "open"
        elif intent_str == "LOCATION":
            action_str = "location"
        elif intent_str == "READ":
            action_str = "read"
        elif intent_str == "REFRESH":
            action_str = "refresh"

        candidates = getattr(result, "search_candidates", []) or []
        yield {
            "type": "meta",
            "action": action_str,
            "intent": intent_str,
            "current_document": getattr(result, "active_document", None) or state_service.get_active_document_info(),
            "results": candidates,
            "ambiguous": getattr(result, "ambiguous", False),
            "success": getattr(result, "success", True),
        }
        msg = getattr(result, "message", str(result))
        yield {"type": "token", "content": msg}
        yield {
            "type": "done",
            "action": action_str,
            "message": msg,
            "current_document": getattr(result, "active_document", None) or state_service.get_active_document_info(),
            "results": candidates,
            "ambiguous": getattr(result, "ambiguous", False),
            "success": getattr(result, "success", True),
        }

    def execute_request(self, parsed: ParsedRequest) -> AgentResult:
        # 1. REFRESH INTENT
        if parsed.intent == IntentType.REFRESH:
            count = indexing_service.build_file_index()
            return AgentResult(
                success=True,
                intent="REFRESH",
                message=f"File index refreshed. {count} documents found.",
                data={"document_count": count},
                active_document=state_service.get_active_document_info(),
            )

        current_doc = state_service.active_document_path

        # 1.5 ALTERNATIVE CANDIDATE INTENT ("Find the other PDF", "Open the other document")
        if parsed.document_reference == "OTHER_CANDIDATE":
            other_doc = state_service.get_other_candidate(extension_filter=parsed.extension_filter)
            if other_doc:
                target_path = Path(other_doc["path"])
                state_service.set_active_document(target_path)
                if parsed.follow_up_action == FollowUpAction.OPEN or parsed.intent == IntentType.OPEN:
                    action_msg = document_service.open_native_file(target_path)
                elif parsed.follow_up_action == FollowUpAction.LOCATION or parsed.intent == IntentType.LOCATION:
                    action_msg = document_service.get_document_location(target_path)
                elif parsed.follow_up_action == FollowUpAction.SUMMARIZE or parsed.intent == IntentType.SUMMARIZE:
                    sum_res = self.summarizer.summarize_file(target_path)
                    action_msg = sum_res.summary
                else:
                    action_msg = f"Found: {target_path.name}"
                return AgentResult(
                    success=True,
                    intent=parsed.intent.value,
                    message=action_msg,
                    data={"selected": target_path.name, "path": str(target_path), "open_status": action_msg},
                    active_document=state_service.get_active_document_info(),
                    search_candidates=[other_doc],
                )
            else:
                return AgentResult(
                    success=False,
                    intent=parsed.intent.value,
                    message="I couldn't find another matching document from our previous search.",
                    error="No other candidate found",
                    active_document=state_service.get_active_document_info(),
                )

        # 2. ASK INTENT
        if parsed.intent == IntentType.ASK:
            target_doc_path = current_doc

            # Target Resolution for document references inside the question
            if parsed.target == TargetType.DOCUMENT_REFERENCE and parsed.document_reference:
                res = self.target_resolver.resolve_reference(parsed.document_reference)
                if res.resolved_path and res.resolved_path.exists():
                    target_doc_path = res.resolved_path
                    # Establish active document context for multi-turn conversations
                    state_service.set_active_document(target_doc_path)

            if target_doc_path is None:
                return AgentResult(
                    success=False,
                    intent="ASK",
                    message="No active document selected. Please select or find a document first.",
                    error="No active document",
                )

            question = parsed.question or parsed.raw_message
            qa_res = self.qa_service.ask(question=question, document_path=target_doc_path)
            return AgentResult(
                success=not qa_res.not_found,
                intent="ASK",
                message=qa_res.answer,
                data=qa_res.to_dict(),
                active_document=state_service.get_active_document_info(),
            )

        # 3. SUMMARIZE INTENT
        if parsed.intent == IntentType.SUMMARIZE:
            if parsed.target == TargetType.CURRENT_DOCUMENT or not parsed.query:
                if current_doc is None:
                    return AgentResult(
                        success=False,
                        intent="SUMMARIZE",
                        message="No active document selected. Please select or find a document first.",
                        error="No active document",
                    )
                sum_res = self.summarizer.summarize_file(current_doc)
                return AgentResult(
                    success=sum_res.error is None,
                    intent="SUMMARIZE",
                    message=sum_res.summary,
                    data=sum_res.to_dict(),
                    active_document=state_service.get_active_document_info(),
                )
            else:
                # Search candidate first, establish active document, then summarize
                search_res = search_service.search_candidates(
                    query=parsed.query,
                    extension_filter=parsed.extension_filter,
                    folder_constraint=parsed.folder_constraint,
                    date_constraint=parsed.date_constraint,
                )
                if not search_res.top_candidate:
                    return AgentResult(
                        success=False,
                        intent="SUMMARIZE",
                        message="No matching document found to summarize.",
                        error="Document not found",
                    )
                target_path = Path(search_res.top_candidate.path)
                state_service.set_active_document(target_path)
                sum_res = self.summarizer.summarize_file(target_path)
                return AgentResult(
                    success=sum_res.error is None,
                    intent="SUMMARIZE",
                    message=sum_res.summary,
                    data=sum_res.to_dict(),
                    active_document=state_service.get_active_document_info(),
                )

        # 4. READ INTENT
        if parsed.intent == IntentType.READ:
            if parsed.target == TargetType.CURRENT_DOCUMENT or not parsed.query:
                if current_doc is None:
                    return AgentResult(
                        success=False,
                        intent="READ",
                        message="No active document selected. Please select or find a document first.",
                        error="No active document",
                    )
                content = document_service.read_document(current_doc)
                return AgentResult(
                    success=not content.startswith("Could not") and not content.startswith("File does not"),
                    intent="READ",
                    message=content,
                    active_document=state_service.get_active_document_info(),
                )
            else:
                target_path = None
                if parsed.absolute_path:
                    target_path = Path(parsed.absolute_path)
                else:
                    search_res = search_service.search_candidates(
                        query=parsed.query,
                        extension_filter=parsed.extension_filter,
                        folder_constraint=parsed.folder_constraint,
                        date_constraint=parsed.date_constraint,
                    )
                    if search_res.top_candidate:
                        target_path = Path(search_res.top_candidate.path)

                if not target_path or not target_path.exists():
                    return AgentResult(
                        success=False,
                        intent="READ",
                        message="No matching document found to read.",
                        error="Document not found",
                    )

                state_service.set_active_document(target_path)
                content = document_service.read_document(target_path)
                return AgentResult(
                    success=True,
                    intent="READ",
                    message=content,
                    active_document=state_service.get_active_document_info(),
                )

        # 5. OPEN INTENT
        if parsed.intent == IntentType.OPEN:
            if parsed.target == TargetType.CURRENT_DOCUMENT or not parsed.query:
                if current_doc is None:
                    return AgentResult(
                        success=False,
                        intent="OPEN",
                        message="No active document selected. Please select or find a document first.",
                        error="No active document",
                    )
                status = document_service.open_native_file(current_doc)
                return AgentResult(
                    success=status.startswith("Opened:"),
                    intent="OPEN",
                    message=status,
                    active_document=state_service.get_active_document_info(),
                )
            else:
                target_path = None
                if parsed.absolute_path:
                    target_path = Path(parsed.absolute_path)
                else:
                    search_res = search_service.search_candidates(
                        query=parsed.query,
                        extension_filter=parsed.extension_filter,
                        folder_constraint=parsed.folder_constraint,
                        date_constraint=parsed.date_constraint,
                    )
                    if search_res.top_candidate:
                        target_path = Path(search_res.top_candidate.path)

                if not target_path or not target_path.exists():
                    return AgentResult(
                        success=False,
                        intent="OPEN",
                        message="No matching document found to open.",
                        error="Document not found",
                    )

                status = document_service.open_native_file(target_path)
                return AgentResult(
                    success=True,
                    intent="OPEN",
                    message=status,
                    active_document=state_service.get_active_document_info(),
                )

        # 6. LOCATION INTENT
        if parsed.intent == IntentType.LOCATION:
            if parsed.target == TargetType.CURRENT_DOCUMENT or not parsed.query:
                if current_doc is None:
                    return AgentResult(
                        success=False,
                        intent="LOCATION",
                        message="No active document selected. Please select or find a document first.",
                        error="No active document",
                    )
                loc_msg = document_service.get_document_location(current_doc)
                return AgentResult(
                    success=True,
                    intent="LOCATION",
                    message=loc_msg,
                    active_document=state_service.get_active_document_info(),
                )
            else:
                search_res = search_service.search_candidates(
                    query=parsed.query,
                    extension_filter=parsed.extension_filter,
                    folder_constraint=parsed.folder_constraint,
                    date_constraint=parsed.date_constraint,
                )
                if not search_res.top_candidate:
                    return AgentResult(
                        success=False,
                        intent="LOCATION",
                        message="No matching document found.",
                        error="Document not found",
                    )
                target_path = Path(search_res.top_candidate.path)
                state_service.set_active_document(target_path)
                loc_msg = document_service.get_document_location(target_path)
                return AgentResult(
                    success=True,
                    intent="LOCATION",
                    message=loc_msg,
                    active_document=state_service.get_active_document_info(),
                )

        # 7. FIND INTENT (Primary Search Intent & Follow-Up Orchestration)
        if parsed.intent == IntentType.FIND or parsed.query:
            if parsed.absolute_path:
                target_path = Path(parsed.absolute_path)
                state_service.set_active_document(target_path)
                if parsed.follow_up_action == FollowUpAction.OPEN:
                    action_msg = document_service.open_native_file(target_path)
                elif parsed.follow_up_action == FollowUpAction.SUMMARIZE:
                    sum_res = self.summarizer.summarize_file(target_path)
                    action_msg = sum_res.summary
                elif parsed.follow_up_action == FollowUpAction.LOCATION:
                    action_msg = document_service.get_document_location(target_path)
                else:
                    action_msg = f"Found: {target_path.name}"

                return AgentResult(
                    success=True,
                    intent="FIND",
                    message=action_msg,
                    data={"selected": target_path.name, "path": str(target_path), "open_status": action_msg},
                    active_document=state_service.get_active_document_info(),
                    search_candidates=[{"path": str(target_path), "name": target_path.name}],
                )

            query = parsed.query if parsed.query is not None else parsed.raw_message
            search_res = search_service.search_candidates(
                query=query,
                extension_filter=parsed.extension_filter,
                folder_constraint=parsed.folder_constraint,
                date_constraint=parsed.date_constraint,
                limit=10,
            )

            candidates = search_res.candidates

            # If 0 candidates found, attempt intelligent fallback reformulation
            if not candidates and (parsed.folder_constraint or parsed.extension_filter):
                # Try relaxing folder constraint first
                if parsed.folder_constraint:
                    fallback_res = search_service.search_candidates(
                        query=query,
                        extension_filter=parsed.extension_filter,
                        folder_constraint=None,
                        date_constraint=parsed.date_constraint,
                        limit=10,
                    )
                    if fallback_res.candidates:
                        candidates = fallback_res.candidates
                        search_res = fallback_res

                # If still no candidates, try relaxing extension filter
                if not candidates and parsed.extension_filter:
                    fallback_res = search_service.search_candidates(
                        query=query,
                        extension_filter=None,
                        folder_constraint=parsed.folder_constraint,
                        date_constraint=parsed.date_constraint,
                        limit=10,
                    )
                    if fallback_res.candidates:
                        candidates = fallback_res.candidates
                        search_res = fallback_res

            # Handle Ambiguity & Low Confidence
            if not candidates or (hasattr(search_res.confidence, "value") and search_res.confidence.value == "LOW") or str(search_res.confidence) == "LOW":
                return AgentResult(
                    success=False,
                    intent="FIND",
                    message="No matching documents could be identified.",
                    search_candidates=[],
                    ambiguous=False,
                    error="No candidates",
                )

            is_ambiguous = (
                (hasattr(search_res.confidence, "value") and search_res.confidence.value == "AMBIGUOUS")
                or str(search_res.confidence) == "AMBIGUOUS"
                or (len(candidates) > 1 and candidates[0].score - candidates[1].score < 10.0)
            )

            cand_info = [
                DocumentInfo.from_path(c.path).to_dict()
                for c in candidates
            ]
            state_service.set_last_search(query, cand_info)

            if is_ambiguous and len(candidates) > 1:
                cand_bullets = "\n".join([f"- {c.name}" for c in candidates[:3]])
                return AgentResult(
                    success=True,
                    intent="FIND",
                    message=f"Multiple matching documents found. Please specify which document you mean:\n\n{cand_bullets}",
                    search_candidates=cand_info,
                    ambiguous=True,
                    active_document=state_service.get_active_document_info(),
                )

            # High confidence top candidate match
            top_candidate = candidates[0]
            target_path = Path(top_candidate.path)
            state_service.set_active_document(target_path)

            # Execute Follow-Up Action
            if parsed.follow_up_action == FollowUpAction.OPEN:
                action_msg = document_service.open_native_file(target_path)
            elif parsed.follow_up_action == FollowUpAction.SUMMARIZE:
                sum_res = self.summarizer.summarize_file(target_path)
                action_msg = sum_res.summary
            elif parsed.follow_up_action == FollowUpAction.LOCATION:
                action_msg = document_service.get_document_location(target_path)
            else:
                action_msg = f"Found: {target_path.name}"

            return AgentResult(
                success=True,
                intent="FIND",
                message=action_msg,
                data={
                    "selected": target_path.name,
                    "path": str(target_path),
                    "open_status": action_msg,
                },
                active_document=state_service.get_active_document_info(),
                search_candidates=cand_info,
                ambiguous=False,
            )

        return AgentResult(
            success=False,
            intent="UNKNOWN",
            message="I don't understand that request.",
            error="Unknown request intent",
        )
