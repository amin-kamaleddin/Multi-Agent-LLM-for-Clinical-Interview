from __future__ import annotations

import os
import json
import uuid
from dataclasses import dataclass
from typing import Optional, Any, List, Dict

from upstash_redis import Redis
from backend.agent_core.interview_agent.models import InterviewState, ModuleLoader
from langchain_core.messages import AIMessage, HumanMessage


def make_thread_id() -> str:
    return f"session_{uuid.uuid4().hex[:8]}"


@dataclass
class SessionData:
    state: InterviewState
    loader_path: str
    red_flag_detected: bool = False
    red_flag_message: str = ""
    diagnosis_result: Optional[Any] = None
    api_key: Optional[str] = None


def _serialize_messages(messages: List[Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for m in messages:
        if isinstance(m, AIMessage):
            out.append({"t": "ai", "c": m.content})
        elif isinstance(m, HumanMessage):
            out.append({"t": "human", "c": m.content})
        else:
            # Fallback to content string if unknown type
            content = getattr(m, "content", str(m))
            out.append({"t": "ai", "c": content})
    return out


def _deserialize_messages(items: List[Dict[str, str]]) -> List[Any]:
    result: List[Any] = []
    for it in items or []:
        t = it.get("t")
        c = it.get("c", "")
        if t == "human":
            result.append(HumanMessage(content=c))
        else:
            result.append(AIMessage(content=c))
    return result


def _serialize_state(state: InterviewState) -> Dict[str, Any]:
    def _jsonable(obj: Any) -> Any:
        if hasattr(obj, "model_dump"):
            try:
                return obj.model_dump()
            except Exception:
                pass
        return obj

    return {
        "current_question_id": state.current_question_id,
        "messages": _serialize_messages(list(state.messages)),
        "conversation_log": state.conversation_log,
        "question_path": state.question_path,
        "evaluator_results": state.evaluator_results,
        "patient_agent": state.patient_agent,
        "red_flag": state.red_flag,
        "module_completed": state.module_completed,
        "ready_for_diagnosis": state.ready_for_diagnosis,
        "diagnosis_content": _jsonable(state.diagnosis_content),
    }


def _deserialize_state(data: Dict[str, Any], loader: ModuleLoader) -> InterviewState:
    st = InterviewState(
        module_loader=loader,
        current_question_id=data.get("current_question_id"),
        messages=_deserialize_messages(data.get("messages", [])),
        conversation_log=data.get("conversation_log", []),
        question_path=data.get("question_path", []),
        evaluator_results=data.get("evaluator_results", []),
        patient_agent=data.get("patient_agent", False),
        red_flag=data.get("red_flag", True),
        module_completed=data.get("module_completed", False),
        ready_for_diagnosis=data.get("ready_for_diagnosis", False),
        diagnosis_content=data.get("diagnosis_content", {}),
    )
    return st


class RedisSessionStore:
    def __init__(self) -> None:
        url = os.getenv("UPSTASH_REDIS_REST_URL")
        token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
        if not url or not token:
            raise RuntimeError("Upstash Redis env vars not set: UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN")
        self.redis = Redis(url=url, token=token)
        self.ttl_seconds = int(os.getenv("SESSION_TTL_SECONDS", "10800"))  # default 3 hours

    def _key(self, thread_id: str) -> str:
        return f"session:{thread_id}"

    def create(self, loader: ModuleLoader, state: InterviewState, loader_path: str) -> str:
        tid = make_thread_id()
        payload = {
            "loader_path": loader_path,
            "red_flag_detected": False,
            "red_flag_message": "",
            "diagnosis_result": None,
            "api_key": None,
            "state": _serialize_state(state),
        }
        key = self._key(tid)
        self.redis.set(key, json.dumps(payload))
        self.redis.expire(key, self.ttl_seconds)
        return tid

    def _load_raw(self, thread_id: str) -> Dict[str, Any]:
        raw = self.redis.get(self._key(thread_id))
        if raw is None:
            raise KeyError(f"Session not found: {thread_id}")
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        if isinstance(raw, str):
            return json.loads(raw)
        return raw

    def get(self, thread_id: str) -> SessionData:
        raw = self._load_raw(thread_id)
        loader = ModuleLoader.from_file(raw["loader_path"])
        state = _deserialize_state(raw["state"], loader)
        # rolling TTL on read
        self.redis.expire(self._key(thread_id), self.ttl_seconds)
        return SessionData(
            state=state,
            loader_path=raw["loader_path"],
            red_flag_detected=raw.get("red_flag_detected", False),
            red_flag_message=raw.get("red_flag_message", ""),
            diagnosis_result=raw.get("diagnosis_result"),
            api_key=raw.get("api_key"),
        )

    def save_state(self, thread_id: str, state: InterviewState) -> None:
        raw = self._load_raw(thread_id)
        raw["state"] = _serialize_state(state)
        key = self._key(thread_id)
        self.redis.set(key, json.dumps(raw))
        self.redis.expire(key, self.ttl_seconds)

    def set_api_key(self, thread_id: str, api_key: Optional[str]) -> None:
        raw = self._load_raw(thread_id)
        raw["api_key"] = api_key
        key = self._key(thread_id)
        self.redis.set(key, json.dumps(raw))
        self.redis.expire(key, self.ttl_seconds)

    def set_red_flag(self, thread_id: str, detected: bool, message: str = "") -> None:
        raw = self._load_raw(thread_id)
        raw["red_flag_detected"] = detected
        raw["red_flag_message"] = message
        key = self._key(thread_id)
        self.redis.set(key, json.dumps(raw))
        self.redis.expire(key, self.ttl_seconds)

    def set_diagnosis(self, thread_id: str, diagnosis: Any) -> None:
        raw = self._load_raw(thread_id)
        # ensure JSON-serializable
        if hasattr(diagnosis, "model_dump"):
            try:
                diagnosis = diagnosis.model_dump()
            except Exception:
                pass
        raw["diagnosis_result"] = diagnosis
        # also mirror into state.diagnosis_content for consistency
        raw_state = raw.get("state", {})
        raw_state["diagnosis_content"] = diagnosis
        raw["state"] = raw_state
        key = self._key(thread_id)
        self.redis.set(key, json.dumps(raw))
        self.redis.expire(key, self.ttl_seconds)

    def clear(self, thread_id: str) -> None:
        self.redis.delete(self._key(thread_id))


SESSION_STORE = RedisSessionStore()


