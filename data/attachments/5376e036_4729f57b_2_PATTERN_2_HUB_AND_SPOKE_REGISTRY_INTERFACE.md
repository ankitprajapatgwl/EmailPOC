# 🏗️ Pattern 2: Supervisor-Worker (Hub-and-Spoke) + Registry + Standardized Agent Interface
## AI-Powered Research Assistant — LangGraph Implementation Guide

> **Architecture:** Hub-and-Spoke (Supervisor-Worker) + Registry Pattern + Standardized Agent Interface
> **Framework:** LangGraph + LangChain
> **Language:** Python 3.11+
> **Principles:** SOLID, OOP, Design Patterns (Hub-and-Spoke, Registry, Command, Facade, Factory)

---

## 📐 Architecture Overview

This pattern combines three complementary ideas:

1. **Hub-and-Spoke (Supervisor-Worker):** The Supervisor is the exclusive hub. ALL communication passes through it. Workers (agents) never communicate with each other directly — even if one worker needs another's output, it requests it via the Supervisor.

2. **Registry Pattern:** A dynamic registry stores agent capabilities, availability, and runtime state. The Supervisor queries the registry to discover capable workers without hardcoding dependencies.

3. **Standardized Agent Interface:** Every agent implements an identical `IAgent` interface (command contract). This means the Supervisor treats all agents uniformly — it doesn't need to know internal agent details to call them.

```
                    ┌──────────────────────────────────────┐
                    │           SUPERVISOR (Hub)            │
                    │                                       │
                    │  ┌──────────────────────────────┐    │
                    │  │       Agent Registry          │    │
                    │  │  (capability map + status)    │    │
                    │  └──────────────────────────────┘    │
                    │                                       │
                    │  ┌──────────────────────────────┐    │
                    │  │    WorkerCommand Dispatcher   │    │
                    │  └──────────────────────────────┘    │
                    └────────────┬────────────┬────────────┘
                                 │  (spoke)   │
                     ┌───────────┘            └───────────┐
                     ▼                                     ▼
              ┌─────────────┐                    ┌──────────────┐
              │  Worker A   │   (Spoke → Hub)    │  Worker B    │
              │  (Agent)    │ ────────────────►  │  (Agent)     │
              └─────────────┘                    └──────────────┘
                     │                                     │
                     └──────────────┬──────────────────────┘
                                    ▼
                           ┌──────────────────┐
                           │   Blackboard     │
                           │  (Shared State)  │
                           └──────────────────┘
```

**Key Traits:**
- All spokes connect only to the hub — workers are isolated from each other
- Standardized `IAgent` interface means Supervisor treats all workers uniformly
- Registry tracks not just capabilities but real-time worker **availability** and **workload**
- `WorkerCommand` objects encapsulate task requests (Command Pattern) — decouples invocation from execution
- Supervisor uses a **Decision Engine** to select the right worker for each command

---

## 📁 Folder Structure

```
research_assistant/
├── agents/
│   ├── __init__.py
│   ├── interfaces/
│   │   ├── __init__.py
│   │   └── i_agent.py              # IAgent abstract interface (Standardized Contract)
│   ├── base_agent.py               # BaseWorkerAgent(IAgent) — shared logic
│   ├── research_agent.py           # ResearchWorker class + internal graph
│   ├── clarifier_agent.py          # ClarifierWorker class + internal graph
│   ├── summarizer_agent.py         # SummarizerWorker class + internal graph
│   ├── critic_agent.py             # CriticWorker class + internal graph
│   └── writer_agent.py             # WriterWorker class + internal graph
│
├── supervisor/
│   ├── __init__.py
│   ├── supervisor.py               # SupervisorHub class — main routing hub
│   ├── decision_engine.py          # DecisionEngine class — routing intelligence
│   └── worker_command.py           # WorkerCommand dataclass — Command Pattern
│
├── registry/
│   ├── __init__.py
│   ├── agent_registry.py           # WorkerRegistry class (Singleton)
│   ├── agent_metadata.py           # WorkerMetadata dataclass
│   └── registry_factory.py        # RegistryFactory — builds and populates registry
│
├── tools/
│   ├── __init__.py
│   ├── search_tools.py             # SearchTool — web/knowledge search
│   ├── validation_tools.py         # ValidationTool — claim checking, schema validation
│   └── formatting_tools.py        # FormattingTool — citations, tone, rendering
│
├── models/
│   ├── __init__.py
│   ├── state.py                    # BlackboardState TypedDict — LangGraph state
│   └── schemas.py                  # Pydantic models for all structured data
│
├── utils/
│   ├── __init__.py
│   ├── cycle_detector.py           # CycleDetector — DFS cycle detection
│   ├── logger.py                   # StructuredLogger
│   └── retry_manager.py           # RetryManager
│
├── config/
│   ├── __init__.py
│   └── settings.py                 # Settings dataclass (Singleton)
│
├── graph/
│   ├── __init__.py
│   └── main_graph.py              # MainGraph — assembles full LangGraph
│
├── tests/
│   ├── test_agents.py
│   ├── test_registry.py
│   ├── test_supervisor.py
│   └── test_decision_engine.py
│
├── requirements.txt
└── main.py
```

---

## 📄 File-by-File Implementation Instructions

---

### `config/settings.py`

**Class:** `Settings` (dataclass, Singleton)

```
Settings:
    Fields:
        - llm_model: str = "gpt-4o"
        - max_retries: int = 2
        - max_hops: int = 6
        - temperature: float = 0.3
        - max_tokens: int = 2048
        - log_level: str = "INFO"
        - langgraph_recursion_limit: int = 30
        - worker_selection_strategy: str = "capability_score"
            # Options: "capability_score" | "round_robin" | "priority_first"
        - enable_parallel_workers: bool = False
            # Pattern 2 supports optional parallel spoke invocation

    Methods:
        - get_instance() -> Settings
        - from_env() -> Settings
```

---

### `models/state.py`

**Class:** `BlackboardState(TypedDict)`

```
BlackboardState fields:
    - original_topic: str
    - refined_query: Optional[RefinedQuery]
    - raw_findings: Annotated[List[Finding], operator.add]
    - summary: Optional[SummaryDocument]
    - critique_reports: Annotated[List[CritiqueReport], operator.add]
    - final_brief: Optional[FinalBrief]
    - call_graph: Annotated[List[CallEdge], operator.add]
    - agent_logs: Annotated[List[AgentLog], operator.add]
    - retry_counts: Dict[str, int]
    - agent_status: Dict[str, AgentStatus]
    - hop_counter: int
    - active_command: Optional[WorkerCommand]     # Current command being executed
    - command_history: List[WorkerCommand]        # All commands dispatched this session
    - supervisor_phase: str                       # "planning" | "executing" | "reviewing" | "finalizing"
    - pending_commands: List[WorkerCommand]       # Queue of commands yet to execute
    - worker_results: Dict[str, Any]              # Keyed by command_id → worker output
    - cycle_detected: bool
    - session_id: str
    - error_messages: Annotated[List[str], operator.add]
```

**Key addition vs Pattern 1:**
- `active_command` / `command_history` / `pending_commands` support the Command Pattern
- `supervisor_phase` tracks which phase of the hub lifecycle we're in
- `worker_results` lets Supervisor aggregate results from multiple workers if parallel mode is on

---

### `models/schemas.py`

**Same Pydantic models as Pattern 1 PLUS:**

```
WorkerCommand:
    - command_id: str           # UUID
    - issued_by: str            # "supervisor"
    - target_worker: str        # "research_agent"
    - task_type: str            # "research" | "clarify" | "summarize" | "critique" | "write"
    - task_payload: dict        # Relevant blackboard slice for this task
    - priority: int             # Execution priority
    - issued_at: datetime
    - completed_at: Optional[datetime]
    - status: CommandStatus     # "pending" | "executing" | "completed" | "failed"
    - result_summary: Optional[str]

CommandStatus (Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"

WorkerCapabilityScore:
    - worker_id: str
    - score: float              # How well this worker matches the task
    - matched_capabilities: List[str]
    - reason: str
```

---

### `agents/interfaces/i_agent.py`

**Purpose:** The standardized contract all workers must implement. This is the cornerstone of Pattern 2 — the Supervisor never depends on concrete classes, only on this interface.

**Design Pattern:** Interface Segregation (ISP), Dependency Inversion (DIP)

**Abstract Interface:** `IAgent(ABC)`

```
IAgent:
    """
    Standardized interface for all worker agents in the Hub-and-Spoke architecture.
    
    Every worker must implement this interface. The Supervisor interacts with
    workers exclusively through this contract — never through concrete classes.
    
    This enforces:
        - Uniform invocation signature
        - Predictable output contract
        - Substitutability (Liskov Substitution Principle)
        - Testability via mock implementations
    """

    Abstract Properties:
        @property
        @abstractmethod
        - agent_id(self) -> str
            """Unique identifier for this worker"""

        @property
        @abstractmethod
        - capabilities(self) -> List[str]
            """List of task tags this worker can handle"""

        @property
        @abstractmethod
        - is_available(self) -> bool
            """True if worker is idle and can accept a command"""

    Abstract Methods:
        @abstractmethod
        - execute(self, command: WorkerCommand, state: BlackboardState) -> BlackboardState
            """
            Execute a WorkerCommand and return updated blackboard state.
            
            This is the ONLY way the Supervisor invokes a worker.
            Workers receive the full state but should only write to fields
            they own (defined in their WorkerMetadata.output_produces).
            
            Args:
                command: WorkerCommand issued by the Supervisor
                state: Current BlackboardState (read + write)
            
            Returns:
                Updated BlackboardState with worker's output written
            
            Raises:
                WorkerExecutionError: If the worker fails to complete
                WorkerInputError: If required input is missing from state
            """

        @abstractmethod
        - validate_command(self, command: WorkerCommand) -> bool
            """
            Validate that a WorkerCommand is executable by this worker.
            Called by Supervisor before dispatching.
            Returns: True if command is valid for this worker
            """

        @abstractmethod
        - get_status(self) -> AgentStatus
            """Return current AgentStatus of this worker"""

        @abstractmethod
        - reset(self) -> None
            """Reset worker state for a new session"""

        @abstractmethod
        - get_metadata(self) -> WorkerMetadata
            """Return this worker's capability metadata"""

        @abstractmethod
        - get_node_function(self) -> Callable
            """Return the LangGraph-compatible node function"""
```

---

### `agents/base_agent.py`

**Purpose:** Partial implementation of `IAgent` with shared logic. Workers inherit this.

**Design Pattern:** Template Method + Facade

**Class:** `BaseWorkerAgent(IAgent, ABC)`

```
BaseWorkerAgent:
    """
    Abstract base class implementing shared IAgent behavior.
    
    Provides:
        - Retry management
        - Status tracking
        - Logging hooks
        - Input validation scaffolding
        - Hop counter management
    
    Workers only need to implement:
        - _execute_core_task(command, state) → core business logic
        - _build_internal_graph() → internal LangGraph sub-graph
        - _validate_input(state) → input precondition check
    """

    Constructor Args:
        - agent_id: str
        - metadata: WorkerMetadata
        - settings: Settings
        - logger: StructuredLogger

    Concrete IAgent Implementations:
        - is_available → state.agent_status[agent_id] == AgentStatus.IDLE
        - get_status() → return current status from internal _status field
        - reset() → set _status = IDLE, reset internal counters
        - get_metadata() → return self._metadata
        - validate_command(command) → check command.task_type in capabilities
        - get_node_function() → lambda: self._adapter_node_fn

        - execute(command, state) → Template Method:
            1. _mark_status(RUNNING)
            2. _validate_input(state)  [abstract — subclass implements]
            3. _check_hop_limit(state) → raise if exceeded
            4. _log_start(command)
            5. result_state = _execute_core_task(command, state)  [abstract]
            6. _log_completion(command)
            7. _mark_status(DONE)
            8. return result_state

    Protected Abstract Methods (subclasses implement):
        @abstractmethod
        - _execute_core_task(command: WorkerCommand, state: BlackboardState) -> BlackboardState

        @abstractmethod
        - _build_internal_graph(self) -> CompiledGraph

        @abstractmethod
        - _validate_input(self, state: BlackboardState) -> None
            """Raise WorkerInputError if required data missing"""

    Protected Concrete Helpers:
        - _mark_status(state, status)
        - _append_log(state, action, input_summary, output_summary)
        - _increment_hop(state)
        - _record_command_completion(state, command, result_summary)
        - _adapter_node_fn(state) → bridges LangGraph node call to execute(command, state)
            """
            LangGraph nodes only receive state. This adapter reconstructs
            the WorkerCommand from state.active_command before calling execute().
            """
```

---

### `agents/research_agent.py`

**Class:** `ResearchWorker(BaseWorkerAgent)`

```
ResearchWorker:
    """
    Worker responsible for gathering raw research findings.
    
    Receives WorkerCommands of type "research" from the Supervisor.
    Reads topic from command.task_payload["topic"].
    Writes List[Finding] to state.raw_findings.
    
    Internal graph handles search, source validation, and recursive refinement.
    """

    Constructor Args:
        - settings: Settings
        - llm: BaseChatModel
        - search_tool: SearchTool       # Injected dependency
        - logger: StructuredLogger

    Private Methods:
        - _build_internal_graph(self) -> CompiledGraph
            """
            Nodes:
                - "topic_extractor": Extract and normalize topic from command payload
                - "search_executor": Call search_tool.search() with topic + sub-queries
                - "source_fetcher": Call search_tool.fetch_source_content() for top results
                - "dedup_filter": Remove duplicate findings by URL hash
                - "relevance_ranker": Score findings by relevance to topic
                - "recursion_guard": Check if recursive search is needed (max depth 2)
            
            Edges:
                - START → "topic_extractor"
                - "topic_extractor" → "search_executor"
                - "search_executor" → "source_fetcher"
                - "source_fetcher" → "dedup_filter"
                - "dedup_filter" → "relevance_ranker"
                - "relevance_ranker" → conditional("recursion_guard"):
                    - "sufficient" → END
                    - "insufficient_depth_ok" → "topic_extractor"  (refined query retry)
                    - "insufficient_depth_exceeded" → END          (return what we have)
            
            Compile with: recursion_limit=3
            """

        - _signal_supervisor(self, state: BlackboardState, findings: List[Finding]) -> BlackboardState
            """
            Write routing intent to state for Supervisor to read.
            
            Does NOT call another worker. Instead writes:
                state.worker_results["research_agent_signal"] = {
                    "next_recommended": "summarizer_agent" | "clarifier_agent" | "critic_agent",
                    "reason": "..."
                }
            The Supervisor's DecisionEngine reads this when planning next command.
            """

    Implementations:
        - _execute_core_task(command, state):
            1. Run _build_internal_graph() result with topic
            2. Parse List[Finding] from graph output
            3. Write to state.raw_findings
            4. Call _signal_supervisor() with findings
            5. Return state

        - _validate_input(state):
            Raise WorkerInputError if neither state.original_topic nor
            state.refined_query is present.

    Metadata:
        WorkerMetadata(
            agent_id="research_worker",
            display_name="Research Worker",
            capabilities=["research", "search", "gather", "fetch"],
            input_requires=["original_topic"],
            output_produces=["raw_findings"],
            is_terminal=False,
            priority=2,
            max_concurrent=1
        )
```

---

### `agents/clarifier_agent.py`

**Class:** `ClarifierWorker(BaseWorkerAgent)`

```
ClarifierWorker:
    """
    Worker responsible for refining vague or ambiguous topics.
    
    Receives WorkerCommands of type "clarify" from the Supervisor.
    Reads raw topic from state.original_topic.
    Writes RefinedQuery to state.refined_query.
    """

    Constructor Args:
        - settings: Settings
        - llm: BaseChatModel
        - logger: StructuredLogger

    Private Methods:
        - _build_internal_graph(self) -> CompiledGraph
            """
            Nodes:
                - "classifier": LLM — classify topic as broad/narrow/clear/contradictory
                - "decomposer": LLM — decompose broad topics into sub-queries
                - "scope_builder": LLM — define scope, constraints, and intent
                - "structured_formatter": Parse LLM output → RefinedQuery
                - "clarity_evaluator": Rule-based — score clarity (0.0–1.0)
                - "self_loop_guard": Allow max 1 internal clarification retry
            
            Edges:
                - START → "classifier"
                - "classifier" → conditional:
                    - "clear" → "scope_builder"
                    - "broad" → "decomposer" → "scope_builder"
                    - "narrow" → "scope_builder"
                    - "contradictory" → "structured_formatter" (flag as contradictory)
                - "scope_builder" → "structured_formatter"
                - "structured_formatter" → "clarity_evaluator"
                - "clarity_evaluator" → conditional:
                    - "clear_enough" → END
                    - "still_unclear" → "self_loop_guard"
                        → if allowed: "classifier"
                        → if blocked: END
            """

    Metadata:
        WorkerMetadata(
            agent_id="clarifier_worker",
            capabilities=["clarify", "refine", "decompose", "scope", "validate_input"],
            priority=1
        )
```

---

### `agents/summarizer_agent.py`

**Class:** `SummarizerWorker(BaseWorkerAgent)`

```
SummarizerWorker:
    """
    Worker responsible for condensing raw findings into structured summaries.
    
    Receives WorkerCommands of type "summarize".
    Reads state.raw_findings.
    Writes SummaryDocument to state.summary.
    """

    Private Methods:
        - _build_internal_graph(self) -> CompiledGraph
            """
            Nodes:
                - "findings_intake": Load and count findings; validate minimum
                - "theme_extractor": LLM — identify themes and recurring arguments
                - "fact_highlighter": LLM — pull out notable/surprising facts
                - "overview_writer": LLM — write executive overview paragraph
                - "summary_assembler": Combine into SummaryDocument
                - "thin_content_detector": Flag if summary lacks substance
            
            Edges:
                - START → "findings_intake"
                - "findings_intake" → conditional:
                    - "sufficient" → "theme_extractor"
                    - "too_sparse" → END (signal: need more research)
                - "theme_extractor" → "fact_highlighter"
                - "fact_highlighter" → "overview_writer"
                - "overview_writer" → "summary_assembler"
                - "summary_assembler" → "thin_content_detector"
                - "thin_content_detector" → conditional:
                    - "substantive" → END
                    - "thin" → END (signal: more research needed)
            """

    Metadata:
        WorkerMetadata(
            agent_id="summarizer_worker",
            capabilities=["summarize", "condense", "analyze", "themes", "insights"],
            priority=3
        )
```

---

### `agents/critic_agent.py`

**Class:** `CriticWorker(BaseWorkerAgent)`

```
CriticWorker:
    """
    Worker responsible for reviewing content quality, accuracy, and completeness.
    
    Receives WorkerCommands of type "critique".
    Reviews what's in state based on command.task_payload["review_target"]:
        - "summary" → review state.summary
        - "raw_findings" → review state.raw_findings
        - "draft" → review state.final_brief (partial)
    Appends CritiqueReport to state.critique_reports.
    """

    Instance Fields:
        - _content_hashes_reviewed: Set[str]    # Deduplicate reviews

    Private Methods:
        - _build_internal_graph(self) -> CompiledGraph
            """
            Nodes:
                - "target_resolver": Extract review target from command payload
                - "dedup_checker": Hash content; skip if already reviewed
                - "gap_analyzer": LLM — logical gaps and unsupported leaps
                - "claim_auditor": LLM + ValidationTool — flag unsupported claims
                - "perspective_checker": LLM — check for missing viewpoints/bias
                - "conflict_detector": ValidationTool — cross-check facts for contradictions
                - "severity_ranker": Classify issues as low/medium/high
                - "report_builder": Compile CritiqueReport
                - "approval_decider": Mark approved=True if no high-severity issues
            
            Edges:
                - START → "target_resolver"
                - "target_resolver" → "dedup_checker"
                - "dedup_checker" → conditional:
                    - "new" → "gap_analyzer"
                    - "duplicate" → END (return cached result)
                - "gap_analyzer" → "claim_auditor"
                - "claim_auditor" → "perspective_checker"
                - "perspective_checker" → "conflict_detector"
                - "conflict_detector" → "severity_ranker"
                - "severity_ranker" → "report_builder"
                - "report_builder" → "approval_decider" → END
            """

        - _get_routing_signal(self, report: CritiqueReport) -> dict
            """
            Map critique severity+type to next recommended worker:
                - high factual → "research_worker"
                - high structural → "summarizer_worker"
                - style/tone → "writer_worker"
                - scope → "clarifier_worker"
                - approved → "writer_worker"
            """

    Metadata:
        WorkerMetadata(
            agent_id="critic_worker",
            capabilities=["critique", "review", "validate", "quality_check", "accuracy"],
            priority=4
        )
```

---

### `agents/writer_agent.py`

**Class:** `WriterWorker(BaseWorkerAgent)`

```
WriterWorker:
    """
    Worker responsible for assembling the final polished research brief.
    
    Receives WorkerCommands of type "write".
    Reads: state.summary, state.critique_reports, state.refined_query
    Writes: FinalBrief to state.final_brief
    
    Terminal worker — when it succeeds, the Supervisor ends the session.
    """

    Private Methods:
        - _build_internal_graph(self) -> CompiledGraph
            """
            Nodes:
                - "content_checker": Verify summary + resolved critiques present
                - "outline_builder": LLM — generate brief outline from summary + query
                - "section_writer": LLM — write each section per outline
                - "citation_builder": FormattingTool.build_citations()
                - "tone_polisher": FormattingTool.apply_tone()
                - "qa_gate": Rule-based — check all sections present and non-empty
                - "brief_compiler": Assemble FinalBrief Pydantic object
            
            Edges:
                - START → "content_checker"
                - "content_checker" → conditional:
                    - "ready" → "outline_builder"
                    - "missing_summary" → END (signal: need summarizer)
                    - "unresolved_critiques" → END (signal: need critic)
                - "outline_builder" → "section_writer"
                - "section_writer" → "citation_builder"
                - "citation_builder" → "tone_polisher"
                - "tone_polisher" → "qa_gate"
                - "qa_gate" → conditional:
                    - "pass" → "brief_compiler" → END
                    - "fail" → "section_writer"  (one revision cycle)
            """

        - _has_unresolved_critiques(reports: List[CritiqueReport]) -> bool
            """Return True if any report has severity 'high' and approved=False"""

    Metadata:
        WorkerMetadata(
            agent_id="writer_worker",
            capabilities=["write", "compile", "format", "finalize", "draft"],
            is_terminal=True,
            priority=5
        )
```

---

### `registry/agent_metadata.py`

**Class:** `WorkerMetadata` (dataclass)

```
WorkerMetadata:
    Fields:
        - agent_id: str
        - display_name: str
        - role: str
        - capabilities: List[str]           # Task tags
        - input_requires: List[str]         # Required blackboard keys
        - output_produces: List[str]        # Written blackboard keys
        - max_retries: int = 2
        - max_concurrent: int = 1           # How many simultaneous commands this worker handles
        - priority: int = 5
        - is_terminal: bool = False
        - accepted_command_types: List[str] # ["research", "clarify", etc.]

    Methods:
        - matches_command(command: WorkerCommand) -> bool
            """Return True if command.task_type in accepted_command_types"""

        - capability_score(task_tags: List[str]) -> float
            """
            Score how well this worker matches a set of task tags.
            Returns: intersection_count / len(task_tags)
            Range: 0.0 (no match) to 1.0 (perfect match)
            """
```

---

### `registry/agent_registry.py`

**Class:** `WorkerRegistry` (Singleton)

```
WorkerRegistry:
    """
    Thread-safe singleton registry for all workers.
    
    Extends Pattern 1's registry concept with:
        - Runtime availability tracking per worker
        - Command-type-based lookup (not just capability tags)
        - Worker load tracking (for future parallel dispatch)
        - Event hooks: on_register, on_unregister, on_status_change
    """

    Class Fields:
        - _instance: Optional[WorkerRegistry] = None
        - _lock: threading.Lock

    Instance Fields:
        - _workers: Dict[str, IAgent]                   # agent_id → IAgent instance
        - _metadata: Dict[str, WorkerMetadata]          # agent_id → metadata
        - _load_counters: Dict[str, int]                # active commands per worker
        - _event_handlers: Dict[str, List[Callable]]    # event_name → handlers
        - _logger: StructuredLogger

    Methods:
        - register(worker: IAgent) -> None
            """
            Register a worker. Extracts metadata via worker.get_metadata().
            Fires on_register event.
            Raises: DuplicateWorkerError if already registered.
            """

        - deregister(agent_id: str) -> None
            """Remove worker and its metadata from registry"""

        - get_worker(agent_id: str) -> IAgent
            """Retrieve worker by ID. Raises: WorkerNotFoundError"""

        - find_available_for_command(command: WorkerCommand) -> List[IAgent]
            """
            Return workers that:
                1. Accept this command type (metadata.matches_command)
                2. Are currently available (worker.is_available)
                3. Have not exceeded max retries for this session
            Sorted by: capability_score desc, then priority asc
            """

        - find_best_for_command(command: WorkerCommand) -> Optional[IAgent]
            """Return the single best available worker for a command"""

        - mark_worker_busy(agent_id: str) -> None
            """Increment load counter, update availability"""

        - mark_worker_free(agent_id: str) -> None
            """Decrement load counter, update availability"""

        - get_all_statuses(self) -> Dict[str, AgentStatus]
            """Return current status snapshot for all workers"""

        - on(event: str, handler: Callable) -> None
            """Register an event handler (Observer pattern)"""

        - _fire_event(event: str, payload: dict) -> None
            """Fire all handlers for an event"""
```

---

### `registry/registry_factory.py`

**Purpose:** Factory that constructs and wires all workers, then populates the registry.

**Design Pattern:** Factory Method

**Class:** `RegistryFactory`

```
RegistryFactory:
    """
    Responsible for instantiating all workers with their dependencies
    and registering them with the WorkerRegistry.
    
    Separates object creation from business logic (SRP + DIP).
    """

    Static Methods:
        - create_registry(
              llm: BaseChatModel,
              settings: Settings,
              logger: StructuredLogger,
              search_tool: SearchTool,
              validation_tool: ValidationTool,
              formatting_tool: FormattingTool
          ) -> WorkerRegistry
            """
            Factory method:
                1. Get/create WorkerRegistry singleton
                2. Instantiate each worker with injected dependencies:
                   - ClarifierWorker(settings, llm, logger)
                   - ResearchWorker(settings, llm, search_tool, logger)
                   - SummarizerWorker(settings, llm, logger)
                   - CriticWorker(settings, llm, validation_tool, logger)
                   - WriterWorker(settings, llm, formatting_tool, logger)
                3. Register each with registry.register(worker)
                4. Return populated registry
            """

        - create_default_registry() -> WorkerRegistry
            """
            Convenience factory using default LLM and mock tools.
            Used in tests and demos.
            """
```

---

### `supervisor/worker_command.py`

**Purpose:** Encapsulate a task request as a Command object.

**Design Pattern:** Command Pattern

**Class:** `WorkerCommand` (Pydantic BaseModel)

```
WorkerCommand:
    """
    Immutable command object issued by the Supervisor to a worker.
    
    Encapsulates:
        - What to do (task_type)
        - Who to do it (target_worker)
        - What data to use (task_payload)
        - Metadata for tracking and replay
    
    Benefits:
        - Supervisor decoupled from worker implementation details
        - Commands can be queued, replayed, cancelled
        - Full audit trail in state.command_history
    """

    Fields:
        - command_id: str = Field(default_factory=lambda: str(uuid4()))
        - issued_by: Literal["supervisor"] = "supervisor"
        - target_worker: str
        - task_type: str          # "research" | "clarify" | "summarize" | "critique" | "write"
        - task_payload: dict      # Relevant data slice for the worker
        - priority: int = 5
        - issued_at: datetime = Field(default_factory=datetime.utcnow)
        - completed_at: Optional[datetime] = None
        - status: CommandStatus = CommandStatus.PENDING
        - retry_number: int = 0
        - parent_command_id: Optional[str] = None     # For chained commands

    Methods:
        - mark_completed(result_summary: str) -> WorkerCommand
            """Return new instance with status=COMPLETED and completed_at set"""

        - mark_failed(error: str) -> WorkerCommand
            """Return new instance with status=FAILED"""

        - retry(self) -> WorkerCommand
            """Return new instance with retry_number incremented"""

        - to_log_dict(self) -> dict
            """Serialize for structured logging"""
```

---

### `supervisor/decision_engine.py`

**Purpose:** The intelligence layer that decides what command to issue next. Keeps routing logic separate from supervisor orchestration.

**Design Pattern:** Strategy Pattern (swappable routing strategies)

**Class:** `DecisionEngine`

```
DecisionEngine:
    """
    Determines the next WorkerCommand to issue based on blackboard state.
    
    Strategies (selectable via settings.worker_selection_strategy):
        - CapabilityScoreStrategy: Score workers by capability match
        - PriorityFirstStrategy: Always pick lowest priority number
        - RoundRobinStrategy: Distribute load evenly
    
    The engine is also responsible for phase management:
        Phase "planning"    → assess what's on blackboard, decide first command
        Phase "executing"   → wait for active command to complete
        Phase "reviewing"   → trigger critique if needed
        Phase "finalizing"  → route to writer when critique is resolved
    """

    Constructor Args:
        - registry: WorkerRegistry
        - cycle_detector: CycleDetector
        - retry_manager: RetryManager
        - settings: Settings
        - logger: StructuredLogger

    Methods:
        - decide_next_command(state: BlackboardState) -> Optional[WorkerCommand]
            """
            Core decision method. Analyzes blackboard and produces next command.
            
            Decision tree:
                1. If hop_counter >= max_hops → return None (signal: stop)
                2. If final_brief present → return None (signal: done)
                3. If cycle_detected → return None
                4. Read worker signal hints from state.worker_results
                5. Advance supervisor_phase based on blackboard completeness
                6. Build WorkerCommand for the determined phase
                7. Validate command against registry
                8. Return command or None
            """

        - _advance_phase(self, state: BlackboardState) -> str
            """
            Determine supervisor_phase based on blackboard:
                - No refined_query → "planning" → target clarifier
                - No raw_findings → "planning" → target researcher
                - No summary → "executing" → target summarizer
                - Summary but no critique → "reviewing" → target critic
                - Critique approved → "finalizing" → target writer
                - final_brief present → "done"
            """

        - _build_command(self, target_worker: str, task_type: str, state: BlackboardState) -> WorkerCommand
            """
            Construct a WorkerCommand with relevant state slice as payload.
            Include only the fields the target worker needs in task_payload.
            """

        - _select_worker_for_command(self, command: WorkerCommand) -> Optional[IAgent]
            """
            Query registry for best available worker.
            Apply cycle detection before confirming selection.
            """
```

---

### `supervisor/supervisor.py`

**Purpose:** The hub — orchestrates command dispatch, receives results, updates blackboard.

**Class:** `SupervisorHub`

```
SupervisorHub:
    """
    Central hub in the Hub-and-Spoke architecture.
    
    Responsibilities:
        1. Maintain supervisor_phase lifecycle
        2. Delegate to DecisionEngine for command planning
        3. Dispatch WorkerCommands to workers via registry
        4. Aggregate worker results back to blackboard
        5. Detect completion conditions
        6. Handle worker failures gracefully
    
    The Supervisor is itself a LangGraph node. It runs on every cycle:
        cycle: [supervisor → worker → supervisor → worker → ... → supervisor → END]
    """

    Constructor Args:
        - registry: WorkerRegistry
        - decision_engine: DecisionEngine
        - retry_manager: RetryManager
        - logger: StructuredLogger

    Methods:
        - run(state: BlackboardState) -> BlackboardState
            """
            Main LangGraph node function.
            
            Steps:
                1. Log current phase and blackboard summary
                2. Check termination conditions
                3. Call decision_engine.decide_next_command(state)
                4. If command is None → set supervisor_phase="done" → return state
                5. Set state.active_command = command
                6. Find target worker via registry.find_best_for_command(command)
                7. Mark worker busy
                8. Invoke worker.execute(command, state) — Hub calls Spoke
                9. Mark worker free
                10. Update state with command result
                11. Append command to state.command_history
                12. Return updated state
            """

        - _is_terminal(self, state: BlackboardState) -> bool
            """
            Return True if:
                - state.final_brief is not None, OR
                - state.hop_counter >= settings.max_hops, OR
                - state.cycle_detected is True
            """

        - _handle_worker_failure(self, state, command, error) -> BlackboardState
            """
            On worker failure:
                1. Log error
                2. Check retry_manager.can_retry(state, command.target_worker)
                3. If can retry → rebuild command with retry_number+1
                4. If exhausted → mark agent as EXHAUSTED, continue with degraded state
            """

        - get_node_function(self) -> Callable
            """Return lambda state: self.run(state)"""

        - route(self, state: BlackboardState) -> str
            """
            LangGraph conditional edge function.
            Called AFTER supervisor runs.
            
            Returns:
                - state.active_command.target_worker  if command was issued
                - "__end__"                           if _is_terminal()
            """
```

---

### `graph/main_graph.py`

**Class:** `MainGraph`

```
MainGraph:
    """
    Assembles the full Hub-and-Spoke LangGraph.
    
    Graph topology:
        - Supervisor is the central hub node
        - Each worker is a spoke node
        - All edges flow: supervisor → worker → supervisor
        - Conditional edges from supervisor determine which spoke activates
    """

    Methods:
        - build(self) -> CompiledGraph
            """
            Steps:
                1. Create StateGraph(BlackboardState)
                2. Add supervisor hub node:
                   graph.add_node("supervisor", supervisor.get_node_function())
                3. For each worker in registry:
                   graph.add_node(worker.agent_id, worker.get_node_function())
                4. Set entry: graph.set_entry_point("supervisor")
                5. Add conditional edges FROM supervisor (routing function):
                   graph.add_conditional_edges(
                       "supervisor",
                       supervisor.route,
                       {
                           "research_worker": "research_worker",
                           "clarifier_worker": "clarifier_worker",
                           "summarizer_worker": "summarizer_worker",
                           "critic_worker": "critic_worker",
                           "writer_worker": "writer_worker",
                           "__end__": END
                       }
                   )
                6. Add return edges: each worker → "supervisor"
                   graph.add_edge("research_worker", "supervisor")
                   ... (all workers return to hub)
                7. Compile with recursion_limit from settings
                8. Return
            """
```

---

## 🔁 Execution Flow (Hub-and-Spoke)

```
User Input → Initial BlackboardState
     │
     ▼
[supervisor] phase=planning
     │  DecisionEngine → WorkerCommand(target=clarifier_worker, type=clarify)
     │
     ▼
[clarifier_worker] ← WorkerCommand ← Hub dispatches
     │  Writes refined_query → returns state
     │
     ▼
[supervisor] phase=planning→executing
     │  Reads worker result → DecisionEngine → WorkerCommand(target=research_worker)
     │
     ▼
[research_worker] ← WorkerCommand ← Hub dispatches
     │  Writes raw_findings → returns state
     │
     ▼
[supervisor] phase=executing
     │  → WorkerCommand(target=summarizer_worker)
     │
     ▼
[summarizer_worker] → Writes summary → returns state
     │
     ▼
[supervisor] phase=reviewing
     │  → WorkerCommand(target=critic_worker, payload={review_target:"summary"})
     │
     ▼
[critic_worker] → Writes critique_report (approved=True) → returns state
     │
     ▼
[supervisor] phase=finalizing
     │  → WorkerCommand(target=writer_worker)
     │
     ▼
[writer_worker] → Writes final_brief → returns state
     │
     ▼
[supervisor] _is_terminal()=True → route → "__end__"
     │
     ▼
Output: FinalBrief
```

---

## 🧩 SOLID Principles Mapping

| Principle | Where Applied |
|-----------|--------------|
| **S** | `IAgent` (interface only), `WorkerCommand` (data only), `DecisionEngine` (routing logic only), `WorkerRegistry` (discovery only) |
| **O** | New workers added by implementing `IAgent` + registering — no Supervisor code changes |
| **L** | Any `IAgent` implementer substitutable; Supervisor never casts to concrete type |
| **I** | `IAgent` has only agent-relevant methods; tools are fully separate interfaces |
| **D** | Supervisor depends on `IAgent` abstraction; `RegistryFactory` injects concrete workers |

---

## 🎯 Key Differentiators from Pattern 1

| Aspect | Pattern 1 | Pattern 2 |
|--------|-----------|-----------|
| Worker-to-worker calls | Workers hint via blackboard | Strictly forbidden — hub-only |
| Command structure | Implicit (blackboard hints) | Explicit `WorkerCommand` objects |
| Routing intelligence | In Supervisor | Separated into `DecisionEngine` |
| Worker interface | `BaseAgent` abstract class | `IAgent` protocol + `BaseWorkerAgent` |
| Phase management | Implicit | Explicit `supervisor_phase` field |
| Worker selection | Capability score | Strategy pattern (swappable) |
| Factory | Manual wiring in main.py | `RegistryFactory` handles all wiring |

---

## 📦 `requirements.txt`

```
langgraph>=0.2.0
langchain>=0.3.0
langchain-openai>=0.2.0
langchain-community>=0.3.0
pydantic>=2.0.0
tavily-python>=0.3.0
beautifulsoup4>=4.12.0
requests>=2.31.0
python-dotenv>=1.0.0
pytest>=8.0.0
```

---

## 🚀 `main.py` Structure

```python
"""
Entry point for Pattern 2: Supervisor-Worker Hub-and-Spoke.

Uses RegistryFactory to wire all dependencies.
Builds hub-and-spoke graph and runs a research query.
"""

# 1. Load Settings
# 2. Initialize StructuredLogger
# 3. Initialize LLM (OpenAI or Anthropic)
# 4. Initialize tools (SearchTool, ValidationTool, FormattingTool)
# 5. Use RegistryFactory.create_registry(llm, settings, logger, tools...)
# 6. Initialize DecisionEngine(registry, cycle_detector, retry_manager, settings, logger)
# 7. Initialize SupervisorHub(registry, decision_engine, retry_manager, logger)
# 8. Build MainGraph(supervisor, registry, settings).build()
# 9. Create initial BlackboardState
# 10. Invoke compiled graph
# 11. Print FinalBrief
```
