import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from ollama import chat
from app.config.settings import OLLAMA_MODEL, DEFAULT_USER_NAME


class IntentType(str, Enum):
    FIND = "FIND"
    LOCATION = "LOCATION"
    OPEN = "OPEN"
    READ = "READ"
    ASK = "ASK"
    SUMMARIZE = "SUMMARIZE"
    REFRESH = "REFRESH"
    UNKNOWN = "UNKNOWN"


class TargetType(str, Enum):
    CURRENT_DOCUMENT = "CURRENT_DOCUMENT"
    DOCUMENT_REFERENCE = "DOCUMENT_REFERENCE"
    SEARCH = "SEARCH"
    MULTIPLE_DOCUMENTS = "MULTIPLE_DOCUMENTS"


class FollowUpAction(str, Enum):
    OPEN = "OPEN"
    SUMMARIZE = "SUMMARIZE"
    LOCATION = "LOCATION"
    ASK = "ASK"


class ParserConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class ParsedRequest:
    intent: IntentType
    query: Optional[str] = None
    question: Optional[str] = None
    folder_constraint: Optional[str] = None
    absolute_path: Optional[str] = None
    extension_filter: Optional[str] = None
    target: Optional[TargetType] = None
    document_reference: Optional[str] = None
    follow_up_action: Optional[FollowUpAction] = None
    date_constraint: Optional[str] = None
    confidence: ParserConfidence = ParserConfidence.HIGH
    parser_source: str = "DETERMINISTIC"
    raw_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "query": self.query,
            "question": self.question,
            "folder_constraint": self.folder_constraint,
            "absolute_path": self.absolute_path,
            "extension_filter": self.extension_filter,
            "target": self.target.value if self.target else None,
            "document_reference": self.document_reference,
            "follow_up_action": self.follow_up_action.value if self.follow_up_action else None,
            "date_constraint": self.date_constraint,
            "confidence": self.confidence.value,
            "parser_source": self.parser_source,
            "raw_message": self.raw_message,
        }


class IntentParser:
    """
    Phase V2.2 Natural-Language Intent & Query Understanding Engine.
    Parses natural user requests into structured ParsedRequest models.
    Supports query cleaning, conversational filler removal, shorthand references,
    document-reference extraction in questions, deep hierarchical path constraints,
    and strict action separation.
    """

    def parse(self, message: str) -> ParsedRequest:
        if not message or not message.strip():
            return ParsedRequest(
                intent=IntentType.UNKNOWN,
                confidence=ParserConfidence.LOW,
                parser_source="DETERMINISTIC",
                raw_message=message or "",
            )

        # 1. Deterministic Parsing First
        parsed_det = self._parse_deterministic(message)
        if parsed_det.confidence != ParserConfidence.LOW:
            return parsed_det

        # 2. LLM Fallback (Ollama qwen2.5:1.5b)
        parsed_llm = self._parse_llm_fallback(message)
        if parsed_llm:
            return parsed_llm

        return parsed_det

    def _parse_deterministic(self, message: str) -> ParsedRequest:
        raw_msg = message.strip()
        # Clean trailing punctuation from message
        clean_msg = re.sub(r'[?.,!;]+$', '', raw_msg).strip()
        msg_lower = clean_msg.lower()

        # Legacy direct command support
        if msg_lower == "refresh":
            return ParsedRequest(
                intent=IntentType.REFRESH,
                confidence=ParserConfidence.HIGH,
                parser_source="DETERMINISTIC",
                raw_message=raw_msg,
            )

        # A. Windows Absolute Path Extraction (supporting spaces in directory/file names)
        win_file_match = re.search(
            r'([a-zA-Z]:[\\/][^"\'\n\r*?<>|]+?\.[a-zA-Z0-9]{2,5})(?=[,;!?]?(\s|$))',
            raw_msg
        )
        win_folder_match = re.search(
            r'([a-zA-Z]:[\\/][^"\'\n\r*?<>|]+?)(?=\s+(?:and|with|for)\b|$|[,;!?]|\.\s)',
            raw_msg
        )
        absolute_path = None
        folder_constraint = None

        if win_file_match:
            absolute_path = win_file_match.group(1).strip()
        elif win_folder_match:
            candidate_path = win_folder_match.group(1).strip()
            if Path(candidate_path).suffix:
                absolute_path = candidate_path
            else:
                folder_constraint = candidate_path

        # B. File Extension Extraction
        extension_filter = None
        if re.search(r'\b(?:pdf|pdf file|pdf document)\b', msg_lower):
            extension_filter = ".pdf"
        elif re.search(r'\b(?:docx|word|word document)\b', msg_lower):
            extension_filter = ".docx"
        elif re.search(r'\b(?:txt|text file|text document)\b', msg_lower):
            extension_filter = ".txt"
        elif re.search(r'\b(?:md|markdown|markdown file)\b', msg_lower):
            extension_filter = ".md"

        # C. Hierarchical & Multi-segment Folder Constraint Extraction
        if not folder_constraint:
            # Check relative multi-segment subpaths (e.g., 'in College/Projects/CampusConnect' or 'College\4th_Year\Internship')
            subpath_match = re.search(
                r'\b(?:in|inside|under|from)\s+(?:the|my|your|a|this)?\s*([a-zA-Z0-9_\-\s]+(?:[/\\][a-zA-Z0-9_\-\s]+)+)(?=\s+(?:and|with|for)\b|$|[.,;!?])',
                raw_msg,
                flags=re.IGNORECASE
            )
            if subpath_match:
                folder_constraint = subpath_match.group(1).strip().replace("\\", "/")
            else:
                # Check for explicit drive constraints (e.g., 'in C drive', 'on D drive', 'from D drive', 'on D:', 'in D:')
                drive_match = re.search(r'\b(?:in|on|from)\s+(?:the\s+)?([c-dC-D])(?:\s*drive\b|:(?:\s|$))|\b([c-dC-D]):(?:\s|$)', raw_msg, flags=re.IGNORECASE)
                if drive_match:
                    d_letter = (drive_match.group(1) or drive_match.group(2)).upper()
                    folder_constraint = f"{d_letter}:"

                # Check single folder names
                folder_match = re.search(
                    r'\b(?:in|inside|under|from)\s+(?:the|my|your|a|this)?\s*(downloads|desktop|documents|college|projects|internship|work|archive|certifications|personal)(?:\s+folder)?\b',
                    msg_lower
                )
                if folder_match:
                    f_name = folder_match.group(1).capitalize()
                    folder_constraint = f"{folder_constraint}/{f_name}" if folder_constraint else f_name

        # Infer Downloads folder if user says "downloaded"
        if not folder_constraint and re.search(r'\b(?:i\s+)?downloaded\b', msg_lower):
            folder_constraint = "Downloads"

        # D. Date Constraint Extraction
        date_constraint = None
        if "yesterday" in msg_lower:
            date_constraint = "yesterday"
        elif "today" in msg_lower:
            date_constraint = "today"
        elif "last week" in msg_lower:
            date_constraint = "last week"
        elif "last month" in msg_lower:
            date_constraint = "last month"
        elif re.search(r'\b(?:recent|recently|latest|most\s+recent)\b', msg_lower):
            date_constraint = "recent"
        else:
            months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
            for m in months:
                if re.search(rf'\b(?:in|from|during|saved\s+in|created\s+in)\s+{m}\b', msg_lower):
                    date_constraint = m
                    break

        # E. Conversational References Check ("it", "this file", "the document we found", "the other PDF")
        is_descriptive_it = bool(re.search(r'\b(?:it\s+(?:was|is|mentions|talks\s+about|discussed|was\s+about))\b', msg_lower))
        is_current_doc_ref = bool(
            re.search(
                r'\b(?:it|this file|this document|that document|the document we(?: just)? found|the file we(?: just)? found|the one we(?: just)? found|the document you(?: just)? found|the file you(?: just)? found|the one you found|the selected document|previous file|previous document|document from earlier|pdf from earlier)\b',
                msg_lower
            )
        )
        if is_descriptive_it and not re.search(r'\b(?:open|summarize|where\s+(?:did\s+i\s+save|is)|tell\s+me\s+where)\s+it\b', msg_lower):
            is_current_doc_ref = False

        is_other_doc_ref = bool(
            re.search(
                r'\b(?:(?:the\s+)?other\s+(?:pdf|file|document|doc|report|one)|another\s+(?:pdf|file|document|doc|report|one)|different\s+(?:pdf|file|document|doc|report|one))\b',
                msg_lower
            )
        )

        # F. Follow-Up Action Extraction
        follow_up_action = None
        if re.search(r'\b(?:and\s+)?(?:open\s+it|open|view\s+it|launch\s+it|launch)\b', msg_lower):
            follow_up_action = FollowUpAction.OPEN
        elif re.search(r'\b(?:and\s+)?(?:summarize\s+it|summarize|give\s+(?:me\s+)?(?:a\s+)?summary)\b', msg_lower):
            follow_up_action = FollowUpAction.SUMMARIZE
        elif re.search(r'\b(?:and\s+)?(?:tell\s+me\s+where\s+it\s+is|tell\s+me\s+where|show\s+(?:file\s+)?path|show\s+location|give\s+(?:file\s+)?path|give\s+(?:folder|location))\b', msg_lower):
            follow_up_action = FollowUpAction.LOCATION

        # G. Alternative Document Reference Short-Circuit
        if is_other_doc_ref:
            intent = IntentType.OPEN if (follow_up_action == FollowUpAction.OPEN or re.search(r'\b(?:open|launch)\b', msg_lower)) else IntentType.FIND
            target = TargetType.DOCUMENT_REFERENCE
            document_reference = "OTHER_CANDIDATE"
            query = "other"
            follow_up = FollowUpAction.OPEN if (follow_up_action == FollowUpAction.OPEN or re.search(r'\b(?:open|launch)\b', msg_lower)) else None
            return ParsedRequest(
                intent=intent,
                query=query,
                target=target,
                document_reference=document_reference,
                extension_filter=extension_filter,
                follow_up_action=follow_up,
                confidence=ParserConfidence.HIGH,
                parser_source="DETERMINISTIC",
                raw_message=raw_msg,
            )

        # G. Intent Classification & Target Resolution
        intent = IntentType.UNKNOWN
        target = None
        question = None
        document_reference = None

        has_find_action = bool(re.search(r'\b(?:find|search|locate|look for|i have a|i saved a file|there is a document|can you find|could you find|retrieve|get|show me)\b', msg_lower))
        is_where_action = bool(re.search(r'\b(?:where did i save|where did i put|where did i store|where is|where are|tell me where|tell me where is|location of|find path of|locate and show path|give location of)\b', msg_lower) or re.match(r'^where\s+.+?\s+is$', msg_lower))
        is_question_action = bool(
            msg_lower.startswith("ask ")
            or re.search(r'^(?:what|how|why|who|which|does|is|can you tell me|tell me)\b', msg_lower)
            or re.search(r'^(?:in|from|inside)\s+.+?[,:]\s*(?:what|how|why|who|which|does|is)\b', msg_lower)
            or (clean_msg.endswith("?") and not has_find_action and not is_where_action)
        )

        if is_question_action and not has_find_action and not (is_where_action and not is_current_doc_ref):
            intent = IntentType.ASK
            q_text = clean_msg
            if msg_lower.startswith("ask "):
                q_text = clean_msg[4:].strip()

            # Check if the question references a target document (DOCUMENT_REFERENCE)
            # e.g., "What tech I used in resume?", "What was the duration in the internship report?", "In Agile methodologies, what is Scrum?"
            doc_ref_match = re.search(
                r'\b(?:in|from|inside)\s+(?:the|my|that|this)?\s*([a-zA-Z0-9_\-\s]+?)(?:\s+(?:report|document|file|docx|pdf|txt|notes|guide|cv|resume))?(?:\?|$)',
                q_text,
                flags=re.IGNORECASE
            )
            # Leading "In <Doc>, what is..."
            leading_doc_match = re.match(
                r'^(?:in|from|inside)\s+([a-zA-Z0-9_\-\s]+?)[,:]\s*(.+)$',
                q_text,
                flags=re.IGNORECASE
            )

            if leading_doc_match:
                document_reference = leading_doc_match.group(1).strip()
                question = leading_doc_match.group(2).strip()
                target = TargetType.DOCUMENT_REFERENCE
            elif doc_ref_match and doc_ref_match.group(1).strip().lower() not in ["it", "this", "that", "the project", "the year", "2024", "2025", "total", "college", "seconds"]:
                candidate_ref = doc_ref_match.group(1).strip()
                # Exclude purely generic non-document nouns
                if candidate_ref.lower() in ["resume", "cv", "curriculum vitae", "internship", "internship report", "agile", "agile methodologies", "campusconnect", "campus connect", "notes", "machine learning notes", "guide", "spec"]:
                    if candidate_ref.lower() == "resume" and re.search(r'\b(?:my|i\s+used|i\s+have|i\s+did|i\s+worked)\b', q_text, flags=re.IGNORECASE):
                        document_reference = "my resume"
                    else:
                        document_reference = candidate_ref
                    # Clean question text by stripping the document reference phrase
                    question = re.sub(rf'\b(?:in|from|inside)\s+(?:the|my|that|this)?\s*{re.escape(candidate_ref)}(?:\s+(?:report|document|file|docx|pdf|txt|notes|guide|cv|resume))?\b', '', q_text, flags=re.IGNORECASE).strip()
                    question = re.sub(r'\s+', ' ', question).strip()
                    target = TargetType.DOCUMENT_REFERENCE
                else:
                    target = TargetType.CURRENT_DOCUMENT
                    question = q_text
            else:
                target = TargetType.CURRENT_DOCUMENT
                question = q_text

        elif is_current_doc_ref and not has_find_action:
            target = TargetType.CURRENT_DOCUMENT
            if re.search(r'\b(?:open|launch|view)\b', msg_lower):
                intent = IntentType.OPEN
            elif re.search(r'\b(?:read|show text)\b', msg_lower):
                intent = IntentType.READ
            elif re.search(r'\b(?:summarize|summary|overview)\b', msg_lower):
                intent = IntentType.SUMMARIZE
            elif re.search(r'\b(?:where|location)\b', msg_lower):
                intent = IntentType.LOCATION
            else:
                intent = IntentType.FIND

        elif has_find_action:
            intent = IntentType.FIND
            target = TargetType.SEARCH

        elif is_where_action:
            intent = IntentType.LOCATION
            target = TargetType.SEARCH

        elif re.search(r'\b(?:open|launch)\b', msg_lower):
            intent = IntentType.OPEN
            target = TargetType.SEARCH if not is_current_doc_ref else TargetType.CURRENT_DOCUMENT

        elif re.search(r'\b(?:read)\b', msg_lower):
            intent = IntentType.READ
            target = TargetType.SEARCH if not is_current_doc_ref else TargetType.CURRENT_DOCUMENT

        elif re.search(r'\b(?:summarize|summary)\b', msg_lower):
            intent = IntentType.SUMMARIZE
            target = TargetType.SEARCH if not is_current_doc_ref else TargetType.CURRENT_DOCUMENT

        else:
            intent = IntentType.FIND
            target = TargetType.SEARCH

        query = None
        if target == TargetType.SEARCH or intent in (IntentType.FIND, IntentType.LOCATION, IntentType.OPEN, IntentType.READ, IntentType.SUMMARIZE):
            query = self._extract_clean_query(clean_msg, folder_constraint, extension_filter)

        confidence = ParserConfidence.HIGH if intent != IntentType.UNKNOWN else ParserConfidence.LOW

        return ParsedRequest(
            intent=intent,
            query=query,
            question=question,
            folder_constraint=folder_constraint,
            absolute_path=absolute_path,
            extension_filter=extension_filter,
            target=target,
            document_reference=document_reference,
            follow_up_action=follow_up_action,
            date_constraint=date_constraint,
            confidence=confidence,
            parser_source="DETERMINISTIC",
            raw_message=raw_msg,
        )

    def _extract_clean_query(
        self,
        clean_msg: str,
        folder: Optional[str] = None,
        ext: Optional[str] = None
    ) -> Optional[str]:
        text = clean_msg.strip()

        # Remove trailing punctuation
        text = re.sub(r'[?.,!;]+$', '', text).strip()

        # Inverted grammar check: "where report internship is" -> "report internship"
        text = re.sub(r'^where\s+(.+?)\s+is$', r'\1', text, flags=re.IGNORECASE).strip()

        # Remove Windows absolute path from query text (with spaces support)
        if folder and ("/" in folder or "\\" in folder or folder.endswith(":")):
            text = text.replace(folder, ' ')
        win_file_match = re.search(
            r'([a-zA-Z]:[\\/][^"\'\n\r*?<>|]+?\.[a-zA-Z0-9]{2,5})(?=[,;!?]?(\s|$))',
            text
        )
        if win_file_match:
            text = text.replace(win_file_match.group(1), ' ')
        win_folder_match = re.search(
            r'([a-zA-Z]:[\\/][^"\'\n\r*?<>|]+?)(?=\s+(?:and|with|for)\b|$|[,;!?]|\.\s)',
            text
        )
        if win_folder_match:
            text = text.replace(win_folder_match.group(1), ' ')
        text = re.sub(r'([a-zA-Z]:\\[^\s"\'\n]+|[a-zA-Z]:/[^\s"\'\n]+)', ' ', text)

        # Remove follow-up phrases and location requests
        text = re.sub(
            r'\b(?:and\s+)?(?:open\s+it|open|view\s+it|launch\s+it|launch|summarize\s+it|summarize|give\s+(?:me\s+)?(?:a\s+)?summary|tell\s+me\s+where\s+it\s+is|tell\s+me\s+where|show\s+(?:file\s+)?path|show\s+location|give\s+(?:file\s+)?path|give\s+(?:folder|location)|where\s+it\s+(?:is|was)\s+(?:stored|located|saved)|where\s+(?:is|was)\s+it\s+(?:stored|located|saved))\b',
            ' ',
            text,
            flags=re.IGNORECASE
        )

        # Remove action prefixes iteratively
        prefix_regex = r'^(?:can you(?: please)?|could you(?: please)?|would you(?: please)?|will you(?: please)?|so like i was wondering if you could find|so like i was wondering if you could|could you please locate the file named|locate the file named|please|hey|hi|hello|um hey|um|uh|like|basically|well|help me|i really need you to help me|i need(?: you)? to|i want(?: you)? to|do you know where|do you know|where did i save|where did i put|where did i store|where is|where are|tell me where is|tell me where|find path of|locate and show path|give location of|show path of|locate|find|search for|search|look for|retrieve|get|show me|i have a|there is a document|i think i saved a file called|i think i saved a file|i think i saved|i saved a file called|i saved a file|i saved|i need to find|me want find|me want|i remember\s+(?:a\s+)?(?:document|file|report|pdf|notes|paper)?(?:\s+(?:about|on|for))?|i recall\s+(?:a\s+)?(?:document|file|report|pdf|notes|paper)?(?:\s+(?:about|on|for))?|i think i have a\s+(?:document|file|report|pdf|notes)?(?:\s+(?:about|on|for))?)\s+'
        while re.search(prefix_regex, text, flags=re.IGNORECASE):
            text = re.sub(prefix_regex, '', text, flags=re.IGNORECASE)

        # Remove content-description lead-ins
        lead_in_regex = r'^(?:i don\'t remember the filename but it was about|i don\'t remember the filename but|i don\'t remember the name but|i don\'t recall the name but|that file where i mentioned|document where i mentioned|document mentioning|file detailing|something about|the document about|that document about|the report on|that report on|report on|the writeup on|the guide for|the one i used for|the one for|show me the document containing|show me the document with|show me the file with|show me the document about|show me the file about)\s+'
        while re.search(lead_in_regex, text, flags=re.IGNORECASE):
            text = re.sub(lead_in_regex, '', text, flags=re.IGNORECASE)

        # Remove "where I discussed / mentioned / was working on / used for"
        text = re.sub(r'\bwhere\s+i\s+(?:discussed|mentioned|wrote\s+about|talked\s+about|was\s+working\s+on|worked\s+on|had|kept)\b', ' ', text, flags=re.IGNORECASE)
        text = re.sub(r'\b(?:i\s+was\s+working\s+on|i\s+worked\s+on|i\s+used\s+for)\b', ' ', text, flags=re.IGNORECASE)

        # Remove "something related to" / "related to" / "containing information about"
        text = re.sub(r'\b(?:something\s+related\s+to|related\s+to|containing\s+information\s+about|containing\s+info\s+about|information\s+about|info\s+about)\b', ' ', text, flags=re.IGNORECASE)

        # Remove "document called" / "file called"
        text = re.sub(r'\b(?:document|file)\s+called\b', ' ', text, flags=re.IGNORECASE)

        # Handle identity mapping:
        # "resume for <name>" -> "<name> resume"
        text = re.sub(r'\bresume\s+for\s+([a-zA-Z0-9_\-]+)\b', r'\1 resume', text, flags=re.IGNORECASE)
        # "with my name on it" / "my name" -> DEFAULT_USER_NAME
        text = re.sub(r'\b(?:with\s+)?my\s+name(?:\s+on\s+it)?\b', DEFAULT_USER_NAME, text, flags=re.IGNORECASE)

        # Remove action suffixes
        text = re.sub(r'\s+(?:find it|can you find it|look for it|locate it|for me|right now please|right now|please|is located|is stored|is saved|located|stored|saved|you know|basically)$', '', text, flags=re.IGNORECASE)

        # Remove date constraints from query text
        text = re.sub(r'\b(?:i\s+)?(?:saved|modified|created|downloaded)?\s*(?:yesterday|today|last\s+week|last\s+month|recently|recent|latest)\b', ' ', text, flags=re.IGNORECASE)
        months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
        for m in months:
            text = re.sub(rf'\b(?:in|from|during|saved\s+in|created\s+in)?\s+{m}\b', ' ', text, flags=re.IGNORECASE)

        # Remove explicit folder constraint phrase if present
        if folder:
            f_clean = folder.replace("\\", "/").split("/")[-1].lower()
            text = re.sub(rf'\b(?:in|inside|under|from)\s+(?:the|my|your|a|this)?\s*{re.escape(f_clean)}(?:\s+folder)?\b', ' ', text, flags=re.IGNORECASE)
            text = re.sub(rf'\b(?:in|inside|under|from)\s+{re.escape(folder.lower())}\b', ' ', text, flags=re.IGNORECASE)
            text = re.sub(r'\b(?:in|inside|under|from)\s*$', ' ', text, flags=re.IGNORECASE)

        # Remove generic folder references
        text = re.sub(r'\b(?:in|inside|under|from)\s+(?:the\s+)?downloads(?:\s+folder)?\b', ' ', text, flags=re.IGNORECASE)
        text = re.sub(r'\bdownloaded(?:\s+for)?\b', ' ', text, flags=re.IGNORECASE)

        # Remove general drive phrases (including "from D drive")
        text = re.sub(r'\b(?:in|on|from)\s+(?:the\s+)?[c-dC-D]\s*drive\b', ' ', text, flags=re.IGNORECASE)

        # Remove generic file type phrases (preserve document stem keywords!)
        text = re.sub(r'\b(?:pdf file|pdf document|word document|text file|markdown file|pdf|docx|txt|md|file)\b', '', text, flags=re.IGNORECASE)

        # Remove "latest" / "recent"
        text = re.sub(r'\b(?:latest|most\s+recent|recently|recent)\b', ' ', text, flags=re.IGNORECASE)

        # Remove pure grammatical filler words
        text = re.sub(r'\b(?:somewhere|called|named|about|a|an|the|this|that|my|your|me|one|document|file)\b', ' ', text, flags=re.IGNORECASE)

        # Remove dangling prepositions at start and end
        text = text.strip()
        text = re.sub(r'^(?:from|in|on|under|inside|for|of|with|about)\s+', '', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'\s+(?:from|in|on|under|inside|for|of|with|about)\s*$', '', text, flags=re.IGNORECASE).strip()

        # Clean multiple spaces and trailing punctuation again
        cleaned = re.sub(r'\s+', ' ', text).strip()
        cleaned = re.sub(r'^[?.,!;:\s]+|[?.,!;:\s]+$', '', cleaned).strip()

        if not cleaned:
            if folder or ext:
                return ""
            return clean_msg

        return cleaned

    def _parse_llm_fallback(self, message: str) -> Optional[ParsedRequest]:
        """
        LLM Fallback parser using local Ollama qwen2.5:1.5b.
        Receives ONLY the user prompt string and returns structured JSON adhering to schema.
        """
        system_prompt = """You are a natural-language request parser.
Analyze the user's input and extract structured request attributes as JSON.

Respond ONLY with a single valid JSON object adhering to this schema:
{
  "intent": "FIND" | "LOCATION" | "OPEN" | "READ" | "ASK" | "SUMMARIZE" | "REFRESH" | "UNKNOWN",
  "query": string or null,
  "question": string or null,
  "folder_constraint": string or null,
  "extension_filter": ".pdf" | ".docx" | ".txt" | ".md" or null,
  "target": "CURRENT_DOCUMENT" | "DOCUMENT_REFERENCE" | "SEARCH" | "MULTIPLE_DOCUMENTS" or null,
  "document_reference": string or null,
  "follow_up_action": "OPEN" | "SUMMARIZE" | "LOCATION" | "ASK" or null,
  "confidence": "HIGH" | "MEDIUM" | "LOW"
}

Do not include markdown code block formatting or explanations. Output raw JSON only."""

        try:
            response = chat(
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
            )
            content = response.message.content.strip()
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)

            data = json.loads(content)
            intent = IntentType(data.get("intent", "UNKNOWN"))
            confidence = ParserConfidence(data.get("confidence", "MEDIUM"))
            target = TargetType(data["target"]) if data.get("target") else None
            follow_up = FollowUpAction(data["follow_up_action"]) if data.get("follow_up_action") else None

            return ParsedRequest(
                intent=intent,
                query=data.get("query"),
                question=data.get("question"),
                folder_constraint=data.get("folder_constraint"),
                extension_filter=data.get("extension_filter"),
                target=target,
                document_reference=data.get("document_reference"),
                follow_up_action=follow_up,
                confidence=confidence,
                parser_source="LLM",
                raw_message=message,
            )
        except Exception:
            return None
