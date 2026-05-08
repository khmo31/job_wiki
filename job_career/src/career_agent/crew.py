from __future__ import annotations

import datetime
import json
import os
import sys
import threading
from pathlib import Path


def _ensure_utf8_stdio() -> None:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            continue


_ensure_utf8_stdio()

from crewai import Agent, Crew, LLM, Process, Task
from crewai.events.event_bus import crewai_event_bus
from crewai.events.types.llm_events import LLMCallCompletedEvent, LLMCallStartedEvent
from crewai.project import CrewBase, agent, crew, task

from .tools import OntologyCheckTool, WikiReadOnlyTool

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LLM_LOG_FILE = PROJECT_ROOT.parent / "job_wiki" / "20_Meta" / "llm_calls.csv"
LLM_CALL_STARTS: dict[str, float] = {}

_LLM_MAX_CONCURRENCY = int(os.getenv("CAREER_AGENT_MAX_CONCURRENCY", "1"))
_LLM_CONCURRENCY_WAIT = float(os.getenv("CAREER_AGENT_CONCURRENCY_WAIT", "20"))
_LLM_SEMAPHORE = threading.Semaphore(_LLM_MAX_CONCURRENCY)


def _ensure_log_header() -> None:
    try:
        LLM_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not LLM_LOG_FILE.exists():
            with LLM_LOG_FILE.open("w", encoding="utf-8") as handle:
                handle.write("timestamp,call_id,model,call_type,duration_s,usage_json,from_agent,from_task,summary\n")
    except Exception:
        return


@crewai_event_bus.on(LLMCallStartedEvent)
def _on_llm_start(source, event: LLMCallStartedEvent):
    try:
        LLM_CALL_STARTS[event.call_id] = datetime.datetime.utcnow().timestamp()
    except Exception:
        return


@crewai_event_bus.on(LLMCallCompletedEvent)
def _on_llm_completed(source, event: LLMCallCompletedEvent):
    try:
        start_ts = LLM_CALL_STARTS.pop(event.call_id, None)
        end_ts = datetime.datetime.utcnow().timestamp()
        duration = end_ts - start_ts if start_ts is not None else None

        try:
            usage = json.dumps(event.usage, ensure_ascii=False)
        except Exception:
            usage = json.dumps({"raw": str(event.usage)}, ensure_ascii=False)

        summary = ""
        try:
            messages = event.messages
            if isinstance(messages, str):
                summary = messages[:200].replace("\n", " ")
            elif isinstance(messages, list) and messages:
                summary = str(messages[0].get("content", ""))[:200].replace("\n", " ")
        except Exception:
            summary = ""

        _ensure_log_header()
        try:
            with LLM_LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(
                    ",".join(
                        [
                            datetime.datetime.utcnow().isoformat(),
                            str(event.call_id),
                            str(event.model or ""),
                            str(event.call_type.value if event.call_type else ""),
                            f"{duration:.3f}" if duration is not None else "",
                            '"' + usage.replace('"', '""') + '"',
                            str(event.__dict__.get("agent_id", "")),
                            str(event.__dict__.get("task_id", "")),
                            '"' + summary.replace('"', '""') + '"',
                        ]
                    )
                    + "\n"
                )
        except Exception:
            pass
    except Exception:
        return


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _build_fast_llm() -> LLM:
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("CAREER_AGENT_FAST_MODEL", "groq/llama-3.3-70b-versatile")
    if os.getenv("CAREER_AGENT_ALLOW_MODEL_OVERRIDE") == "1":
        model = os.getenv("CAREER_AGENT_FAST_MODEL", model)
    max_tokens = int(os.getenv("CAREER_AGENT_MAX_TOKENS", "128"))
    return LLM(
        model=model,
        api_key=api_key,
        provider="groq",
        temperature=float(os.getenv("CAREER_AGENT_FAST_TEMPERATURE", "0.0")),
        timeout=_env_int("CAREER_AGENT_FAST_TIMEOUT", 20),
        max_retries=_env_int("CAREER_AGENT_FAST_MAX_RETRIES", 0),
        additional_params={"max_tokens": max_tokens},
    )


def _build_smart_llm() -> LLM:
    api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1")
    model = os.getenv("CAREER_AGENT_SMART_MODEL", "deepseek-ai/deepseek-v4-pro")
    max_tokens = int(os.getenv("CAREER_AGENT_MAX_TOKENS", "128"))
    return LLM(
        model=model,
        api_key=api_key,
        base_url=base_url,
        provider="openai",
        temperature=float(os.getenv("CAREER_AGENT_SMART_TEMPERATURE", "0.2")),
        timeout=_env_int("CAREER_AGENT_SMART_TIMEOUT", 45),
        max_retries=_env_int("CAREER_AGENT_SMART_MAX_RETRIES", 0),
        additional_params={"max_tokens": max_tokens},
    )


@CrewBase
class CareerAgentCrew:
    """CrewAI orchestration for the career judgment workflow."""

    agents_config = str(PROJECT_ROOT / "config" / "agents.yaml")
    tasks_config = str(PROJECT_ROOT / "config" / "tasks.yaml")
    fast_llm = _build_fast_llm()
    smart_llm = _build_smart_llm()
    evaluator_llm = smart_llm if os.getenv("CAREER_AGENT_USE_SMART_EVALUATOR") == "1" else fast_llm

    @agent
    def career_entity_mapper(self) -> Agent:
        return Agent(
            config=self.agents_config["career_entity_mapper"],
            tools=[OntologyCheckTool()],
            llm=self.fast_llm,
            verbose=True,
            allow_delegation=False,
            max_iter=int(os.getenv("CAREER_AGENT_MAX_ITER", "2")),
            max_execution_time=30,
        )

    @agent
    def final_evaluator(self) -> Agent:
        return Agent(
            config=self.agents_config["final_evaluator"],
            tools=[WikiReadOnlyTool()],
            llm=self.evaluator_llm,
            verbose=True,
            allow_delegation=False,
            max_iter=int(os.getenv("CAREER_AGENT_FINAL_MAX_ITER", "4")),
            max_execution_time=60,
            step_callback=None,
        )

    @task
    def entity_mapping_task(self) -> Task:
        return Task(config=self.tasks_config["entity_mapping_task"])

    @task
    def final_evaluation_task(self) -> Task:
        return Task(config=self.tasks_config["final_evaluation_task"])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.career_entity_mapper(), self.final_evaluator()],
            tasks=[self.entity_mapping_task(), self.final_evaluation_task()],
            process=Process.sequential,
            verbose=True,
        )