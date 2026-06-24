# 🏗️ Pattern 1: Supervisor + Agent Registry Pattern
## AI-Powered Research Assistant — LangGraph Implementation Guide

> **Architecture:** Supervisor + Agent Registry
> **Framework:** LangGraph + LangChain
> **Language:** Python 3.11+
> **Principles:** SOLID, OOP, Design Patterns (Registry, Strategy, Template Method, Observer)

---

## 📐 Architecture Overview

In this pattern, a **central Supervisor** is the sole decision-maker. It does not contain business logic — instead, it queries an **Agent Registry** to discover and route tasks to registered agents. Agents register themselves with metadata (capabilities, input/output contracts), and the Supervisor dynamically selects the right agent via the registry.

```
┌──────────────────────────────────────────────────────────┐
│                    Supervisor Node                        │
│   ┌──────────────────────────────────────────────────┐   │
│   │              Agent Registry                       │   │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │   │
│   │  │ Research │ │Clarifier │ │   Summarizer     │  │   │
│   │  │  Agent   │ │  Agent   │ │     Agent        │  │   │
│   │  └──────────┘ └──────────┘ └──────────────────┘  │   │
│   │  ┌──────────┐ ┌──────────┐                        │   │
│   │  │  Critic  │ │  Writer  │                        │   │
│   │  │  Agent   │ │  Agent   │                        │   │
│   │  └──────────┘ └──────────┘                        │   │
│   └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
            │
            ▼
    ┌───────────────┐
    │  Blackboard   │  ← Shared State (LangGraph State)
    │  (State Dict) │
    └───────────────┘
```

**Key Traits:**
- Supervisor reads the blackboard, selects an agent from registry, invokes it
- Agents are **stateless workers** — they read/write to blackboard only
- Registry is a **singleton** with agent metadata and capability tags
- No agent knows about other agents — all routing lives in the Supervisor

---

## 📁 Folder Structure

```
research_assistant/
├── agents/
│   ├── __init__.py
│   ├── base_agent.py               # Abstract base class (Template Method pattern)
│   ├── research_agent.py           # ResearchAgent class + its sub-graph
│   ├── clarifier_agent.py          # ClarifierAgent class + its sub-graph
│   ├── summarizer_agent.py         # SummarizerAgent class + its sub-graph
│   ├── critic_agent.py             # CriticAgent class + its sub-graph
│   └── writer_agent.py             # WriterAgent class + its sub-graph
│
├── supervisor/
│   ├── __init__.py
│   └── supervisor.py               # SupervisorNode class + routing logic
│
├── registry/
│   ├── __init__.py
│   ├── agent_registry.py           # AgentRegistry singleton class
│   └── agent_metadata.py           # AgentMetadata dataclass
│
├── tools/
│   ├── __init__.py
│   ├── search_tools.py             # Web search, Wikipedia fetch, source validation
│   ├── validation_tools.py         # Schema validation, claim checking
│   └── formatting_tools.py         # Output formatting, citation generation
│
├── models/
│   ├── __init__.py
│   ├── state.py                    # BlackboardState TypedDict (LangGraph state)
│   └── schemas.py                  # Pydantic models for structured outputs
│
├── utils/
│   ├── __init__.py
│   ├── cycle_detector.py           # CycleDetector class
│   ├── logger.py                   # StructuredLogger class
│   └── retry_manager.py            # RetryManager class
│
├── config/
│   ├── __init__.py
│   └── settings.py                 # Settings dataclass + constants
│
├── graph/
│   ├── __init__.py
│   └── main_graph.py               # MainGraph class — assembles the full LangGraph
│
├── tests/
│   ├── test_agents.py
│   ├── test_registry.py
│   └── test_supervisor.py
│
├── requirements.txt
└── main.py                         # Entry point
```

---

## 📄 File-by-File Implementation Instructions

---

### `config/settings.py`

**Purpose:** Centralized configuration — all constants, LLM settings, limits.

**Class:** `Settings` (dataclass, Singleton via `__new__`)

**Contents:**
```
Settings:
    Fields:
        - llm_model: str = "gpt-4o"
        - max_retries: int = 2
        - max_hops: int = 6
        - temperature: float = 0.3
        - max_tokens: int = 2048
        - log_level: str = "INFO"
        - langgraph_recursion_limit: int = 25
        - agent_names: dict[str, str]  # mapping of role → display name

    Methods:
        - get_instance() -> Settings   # Singleton accessor
        - from_env() -> Settings       # Load from environment variables
```

**SOLID:** Single Responsibility — only configuration. Open/Closed — extend via subclass.

---

### `models/state.py`

**Purpose:** Define the shared blackboard as a LangGraph `TypedDict` state.

**Class:** `BlackboardState(TypedDict)`

```
BlackboardState fields:
    - original_topic: str
    - refined_query: Optional[RefinedQuery]         # Written by Clarifier
    - raw_findings: List[Finding]                   # Written by Research
    - summary: Optional[SummaryDocument]            # Written by Summarizer
    - critique_reports: List[CritiqueReport]        # Written by Critic
    - final_brief: Optional[FinalBrief]             # Written by Writer
    - call_graph: List[CallEdge]                    # Written by all agents
    - agent_logs: List[AgentLog]                    # Written by all agents
    - retry_counts: Dict[str, int]                  # Per-agent counters
    - agent_status: Dict[str, AgentStatus]          # idle/running/done/failed/exhausted
    - hop_counter: int                              # Global hop counter
    - current_agent: Optional[str]                  # Which agent Supervisor last routed to
    - supervisor_decision: Optional[str]            # Supervisor's routing decision + reason
    - error_messages: List[str]                     # Any errors captured
    - cycle_detected: bool                          # Flag set by cycle detector
    - session_id: str                               # Unique session ID
```

**Note:** Use `Annotated[List[X], operator.add]` for list fields that agents append to (call_graph, agent_logs, critique_reports) so LangGraph merges them correctly across parallel branches.

---

### `models/schemas.py`

**Purpose:** Pydantic models for all structured data objects passed on the blackboard.

**Classes to define:**

```
Finding:
    - content: str
    - source: str
    - relevance_score: float
    - timestamp: datetime

RefinedQuery:
    - original: str
    - refined: str
    - scope: str
    - constraints: List[str]
    - sub_queries: List[str]

SummaryDocument:
    - overview: str
    - key_points: List[str]
    - notable_facts: List[str]
    - confidence_score: float

CritiqueReport:
    - reviewed_by: str          # "critic_agent"
    - target_content: str       # What was reviewed
    - issues: List[Issue]
    - overall_severity: Literal["low", "medium", "high", "none"]
    - suggestions: List[str]
    - approved: bool

Issue:
    - description: str
    - severity: Literal["low", "medium", "high"]
    - location: str

FinalBrief:
    - title: str
    - sections: List[Section]
    - key_findings: List[str]
    - citations: List[str]
    - metadata: BriefMetadata

Section:
    - heading: str
    - content: str

BriefMetadata:
    - topic: str
    - session_id: str
    - agents_involved: List[str]
    - total_hops: int
    - generated_at: datetime

CallEdge:
    - caller: str
    - callee: str
    - hop_number: int
    - reason: str
    - timestamp: datetime

AgentLog:
    - agent_name: str
    - action: str
    - input_summary: str
    - output_summary: str
    - timestamp: datetime
    - duration_ms: float

AgentStatus (Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    EXHAUSTED = "exhausted"
```

---

### `registry/agent_metadata.py`

**Purpose:** Data contract describing each agent's identity and capabilities.

**Class:** `AgentMetadata` (dataclass)

```
AgentMetadata:
    Fields:
        - agent_id: str                         # Unique key: "research_agent"
        - display_name: str                     # Human-readable: "Research Agent"
        - role: str                             # Primary role description
        - capabilities: List[str]               # Tags: ["search", "gather", "recurse"]
        - input_requires: List[str]             # Blackboard keys this agent needs
        - output_produces: List[str]            # Blackboard keys this agent writes
        - max_retries: int                      # Per-agent retry limit
        - priority: int                         # Routing priority (lower = higher priority)
        - is_terminal: bool                     # Can this agent be the final step?

    Methods:
        - can_handle(task_tags: List[str]) -> bool
            """Returns True if any capability tag matches a task tag"""
        - to_dict() -> dict
            """Serializes metadata for logging"""
```

---

### `registry/agent_registry.py`

**Purpose:** Singleton registry that stores, discovers, and resolves agents.

**Design Pattern:** Registry Pattern + Singleton

**Class:** `AgentRegistry`

```
AgentRegistry:
    Class-level:
        - _instance: Optional[AgentRegistry] = None
        - _lock: threading.Lock

    Instance Fields:
        - _registry: Dict[str, AgentMetadata]           # agent_id → metadata
        - _agent_instances: Dict[str, BaseAgent]         # agent_id → live instance
        - _logger: StructuredLogger

    Methods:
        - __new__(cls) -> AgentRegistry
            """Enforce singleton via double-checked locking"""

        - register(agent: BaseAgent, metadata: AgentMetadata) -> None
            """
            Register an agent with its metadata.
            Raises: DuplicateAgentError if agent_id already registered.
            Logs: registration event with agent_id and capabilities
            """

        - unregister(agent_id: str) -> None
            """Remove an agent from the registry"""

        - get_agent(agent_id: str) -> BaseAgent
            """
            Retrieve agent instance by ID.
            Raises: AgentNotFoundError if not registered.
            """

        - get_metadata(agent_id: str) -> AgentMetadata
            """Retrieve metadata for an agent"""

        - find_by_capability(capability: str) -> List[AgentMetadata]
            """Return all agents that have the given capability tag"""

        - find_best_for_task(task_tags: List[str]) -> Optional[AgentMetadata]
            """
            Score agents by how many task_tags match their capabilities.
            Return the highest-scoring agent. Tie-break by priority field.
            """

        - list_all() -> List[AgentMetadata]
            """Return all registered agent metadata sorted by priority"""

        - get_registry_snapshot() -> dict
            """Return full registry state as dict for debugging/logging"""
```

**Docstring contract:** Every method must have:
- Summary line
- Args section
- Returns section
- Raises section (if applicable)
- Example usage in docstring

---

### `agents/base_agent.py`

**Purpose:** Abstract base class all agents inherit from. Defines the Template Method pattern — the skeleton of what every agent does.

**Design Patterns:** Template Method, Strategy (for decision-making), Observer (for logging)

**Abstract Class:** `BaseAgent(ABC)`

```
BaseAgent:
    Constructor Args:
        - agent_id: str
        - settings: Settings
        - logger: StructuredLogger

    Abstract Methods (subclasses MUST implement):
        - _execute_primary_task(state: BlackboardState) -> BlackboardState
            """Core agent logic — what this agent does"""

        - _should_delegate(state: BlackboardState) -> Optional[str]
            """
            Return the agent_id to delegate to, or None.
            This is called by the Supervisor — agents do NOT call each other.
            The agent communicates its intent by writing to blackboard.
            """

        - _validate_input(state: BlackboardState) -> bool
            """Check that required blackboard keys are present before running"""

        - get_node_function(self) -> Callable
            """Return the LangGraph-compatible node function"""

    Concrete Methods (provided by base, can override):
        - run(state: BlackboardState) -> BlackboardState
            """
            Template method — the fixed execution skeleton:
            1. Validate input
            2. Check retry count
            3. Log start
            4. Execute _execute_primary_task
            5. Log completion
            6. Update blackboard (status, logs, hop_counter)
            7. Return updated state
            """

        - _increment_retry(state: BlackboardState) -> BlackboardState
            """Increment this agent's retry count in state.retry_counts"""

        - _mark_status(state: BlackboardState, status: AgentStatus) -> BlackboardState
            """Write agent_id → status to state.agent_status"""

        - _append_log(state: BlackboardState, action: str, ...) -> BlackboardState
            """Append structured log entry to state.agent_logs"""

        - _append_call_edge(state: BlackboardState, callee: str, reason: str) -> BlackboardState
            """Record a routing intent edge to state.call_graph"""

        - _is_exhausted(state: BlackboardState) -> bool
            """Returns True if retry_counts[agent_id] >= settings.max_retries"""

    Properties:
        - agent_id: str
        - display_name: str (from metadata)
```

---

### `agents/research_agent.py`

**Purpose:** Gathers raw research findings. Builds its own sub-graph internally.

**Class:** `ResearchAgent(BaseAgent)`

```
ResearchAgent:
    Constructor Args:
        - settings: Settings
        - llm: BaseChatModel          # Injected LLM (Dependency Inversion)
        - search_tool: SearchTool     # Injected tool (from tools/search_tools.py)
        - logger: StructuredLogger

    Private Methods:
        - _build_internal_graph(self) -> CompiledGraph
            """
            Build a LangGraph StateGraph for internal research logic.
            
            Nodes:
                - "query_parser": Parse and validate the topic
                - "web_search": Call search_tool.search()
                - "source_validator": Call validation_tools.validate_sources()
                - "findings_formatter": Format raw results into Finding objects
                - "self_recurse_check": Decide if recursive search is needed
            
            Edges:
                - START → "query_parser"
                - "query_parser" → "web_search"
                - "web_search" → "source_validator"
                - "source_validator" → "findings_formatter"
                - "findings_formatter" → conditional("self_recurse_check"):
                    - "findings_sufficient" → END
                    - "findings_insufficient" → "query_parser"  (depth-limited recursion)
            
            Compile with: recursion_limit=3 to cap internal recursion.
            Store as: self._graph
            """

        - _decide_delegation(self, findings: List[Finding]) -> Optional[str]
            """
            Pure logic — no LLM call needed.
            Rules:
                - len(findings) == 0 → suggest "clarifier_agent"
                - any conflicting sources → suggest "critic_agent"
                - findings sufficient → suggest "summarizer_agent"
                - simple topic → suggest "writer_agent" (rare fast path)
            Write suggestion to blackboard field: supervisor_decision hint
            Return None (Supervisor reads blackboard to decide next step)
            """

    Implementations of Abstract Methods:
        - _execute_primary_task(state):
            1. Extract topic from state.refined_query or state.original_topic
            2. Invoke self._graph with topic as input
            3. Parse graph output into List[Finding]
            4. Write findings to state.raw_findings
            5. Call _decide_delegation() to hint Supervisor
            6. Return updated state

        - _validate_input(state):
            Requires: state.original_topic is not empty

        - _should_delegate(state):
            Read own hint from blackboard, return it

        - get_node_function():
            Return lambda state: self.run(state)

    Metadata (define as class-level constant):
        AgentMetadata(
            agent_id="research_agent",
            capabilities=["search", "gather", "fetch", "research"],
            input_requires=["original_topic"],
            output_produces=["raw_findings"],
            is_terminal=False,
            priority=2
        )
```

**Tools used (imported from `tools/search_tools.py`):**
- `SearchTool.search(query: str, max_results: int) -> List[dict]`
- `SearchTool.fetch_source_content(url: str) -> str`

---

### `agents/clarifier_agent.py`

**Purpose:** Refines vague topics into structured queries.

**Class:** `ClarifierAgent(BaseAgent)`

```
ClarifierAgent:
    Constructor Args:
        - settings: Settings
        - llm: BaseChatModel
        - logger: StructuredLogger

    Private Methods:
        - _build_internal_graph(self) -> CompiledGraph
            """
            Nodes:
                - "ambiguity_detector": LLM call — classify topic as broad/narrow/clear/contradictory
                - "query_decomposer": LLM call — break broad topic into sub-queries
                - "scope_definer": LLM call — define scope + constraints
                - "refinement_validator": Check if refined query is acceptable
                - "loop_guard": Check self-loop counter (max 1 internal loop)
            
            Edges:
                - START → "ambiguity_detector"
                - "ambiguity_detector" → conditional:
                    - "clear" → "scope_definer"
                    - "broad" → "query_decomposer" → "scope_definer"
                    - "narrow" → "scope_definer"
                    - "contradictory" → END (with error flag)
                - "scope_definer" → "refinement_validator"
                - "refinement_validator" → conditional:
                    - "acceptable" → END
                    - "still_unclear" → "loop_guard"
                        - if loop_guard allows → "ambiguity_detector" (one retry)
                        - if loop_guard blocks → END (return best attempt)
            """

        - _format_refined_query(self, llm_response: str) -> RefinedQuery
            """Parse LLM JSON output into RefinedQuery Pydantic model"""

    Implementations:
        - _execute_primary_task(state):
            1. Get topic from state.original_topic
            2. Run internal graph
            3. Write RefinedQuery to state.refined_query
            4. Hint Supervisor: "research_agent" (or "writer_agent" if it's a writing request)

        - _validate_input(state):
            Requires: state.original_topic is not empty

    Metadata:
        AgentMetadata(
            agent_id="clarifier_agent",
            capabilities=["clarify", "refine", "decompose", "scope"],
            input_requires=["original_topic"],
            output_produces=["refined_query"],
            is_terminal=False,
            priority=1       # Highest priority — clarify before anything else
        )
```

---

### `agents/summarizer_agent.py`

**Purpose:** Condenses raw findings into structured summaries.

**Class:** `SummarizerAgent(BaseAgent)`

```
SummarizerAgent:
    Constructor Args:
        - settings: Settings
        - llm: BaseChatModel
        - logger: StructuredLogger

    Private Methods:
        - _build_internal_graph(self) -> CompiledGraph
            """
            Nodes:
                - "findings_loader": Load and validate raw_findings from blackboard
                - "theme_extractor": LLM call — extract key themes and arguments
                - "insight_generator": LLM call — generate notable facts and insights
                - "summary_compiler": LLM call — compile into SummaryDocument structure
                - "completeness_checker": Rule-based — check if summary is substantive
            
            Edges:
                - START → "findings_loader"
                - "findings_loader" → conditional:
                    - "sufficient" → "theme_extractor"
                    - "insufficient" → END (with hint: need more research)
                - "theme_extractor" → "insight_generator"
                - "insight_generator" → "summary_compiler"
                - "summary_compiler" → "completeness_checker"
                - "completeness_checker" → conditional:
                    - "complete" → END
                    - "incomplete" → END (with hint: needs more research)
            """

        - _check_findings_sufficiency(self, findings: List[Finding]) -> bool
            """
            Heuristic:
                - Minimum 3 findings required
                - Total content length > 500 characters
                - At least 1 source with relevance_score > 0.6
            """

    Implementations:
        - _execute_primary_task(state):
            1. Run internal graph
            2. If insufficient → hint Supervisor: "research_agent"
            3. If summary contains unsupported claims → hint Supervisor: "critic_agent"
            4. If successful → hint Supervisor: "writer_agent"
            5. Write SummaryDocument to state.summary

    Metadata:
        AgentMetadata(
            agent_id="summarizer_agent",
            capabilities=["summarize", "analyze", "condense", "themes"],
            input_requires=["raw_findings"],
            output_produces=["summary"],
            is_terminal=False,
            priority=3
        )
```

---

### `agents/critic_agent.py`

**Purpose:** Reviews any content for quality, accuracy, bias, completeness.

**Class:** `CriticAgent(BaseAgent)`

```
CriticAgent:
    Constructor Args:
        - settings: Settings
        - llm: BaseChatModel
        - validation_tool: ValidationTool    # from tools/validation_tools.py
        - logger: StructuredLogger

    Instance Fields:
        - _reviewed_content_hashes: Set[str]    # Track reviewed content to avoid duplicates

    Private Methods:
        - _build_internal_graph(self) -> CompiledGraph
            """
            Nodes:
                - "content_selector": Determine what to review (summary vs raw_findings vs final_brief)
                - "duplicate_check": Hash content, skip if already reviewed
                - "logical_gap_detector": LLM call — find logical inconsistencies
                - "claim_validator": LLM call — flag unsupported claims
                - "bias_detector": LLM call — check for missing perspectives
                - "critique_compiler": Compile all issues into CritiqueReport
                - "severity_assessor": Overall severity: low/medium/high/none
            
            Edges:
                - START → "content_selector"
                - "content_selector" → "duplicate_check"
                - "duplicate_check" → conditional:
                    - "new_content" → "logical_gap_detector"
                    - "already_reviewed" → END (skip)
                - "logical_gap_detector" → "claim_validator"
                - "claim_validator" → "bias_detector"
                - "bias_detector" → "critique_compiler"
                - "critique_compiler" → "severity_assessor" → END
            """

        - _hash_content(self, content: str) -> str
            """SHA-256 hash of content string for deduplication"""

        - _build_routing_hint(self, report: CritiqueReport) -> str
            """
            Derive next-agent hint from critique:
                - high severity factual → "research_agent"
                - high severity structural → "summarizer_agent"
                - stylistic/tone → "writer_agent"
                - topic scope issue → "clarifier_agent"
                - approved (no critical issues) → "writer_agent"
            """

    Implementations:
        - _execute_primary_task(state):
            1. Run internal graph to produce CritiqueReport
            2. Append report to state.critique_reports
            3. Apply _build_routing_hint() → write hint to blackboard
            4. Return updated state

    Metadata:
        AgentMetadata(
            agent_id="critic_agent",
            capabilities=["review", "critique", "validate", "quality", "accuracy"],
            input_requires=["summary"],      # Minimum required; can also review raw_findings
            output_produces=["critique_reports"],
            is_terminal=False,
            priority=4
        )
```

**Tools used (imported from `tools/validation_tools.py`):**
- `ValidationTool.check_claim(claim: str, sources: List[str]) -> ClaimCheckResult`
- `ValidationTool.detect_contradictions(findings: List[Finding]) -> List[Contradiction]`

---

### `agents/writer_agent.py`

**Purpose:** Assembles everything into a polished final research brief.

**Class:** `WriterAgent(BaseAgent)`

```
WriterAgent:
    Constructor Args:
        - settings: Settings
        - llm: BaseChatModel
        - formatting_tool: FormattingTool   # from tools/formatting_tools.py
        - logger: StructuredLogger

    Private Methods:
        - _build_internal_graph(self) -> CompiledGraph
            """
            Nodes:
                - "content_assembler": Gather summary, critique_reports, original_topic
                - "completeness_check": Verify all required sections are present
                - "tone_formatter": LLM call — apply consistent tone and structure
                - "citation_builder": Call formatting_tool.build_citations()
                - "section_writer": LLM call — write each section of the brief
                - "internal_qa": Rule-based — final quality gate before delivery
                - "brief_finalizer": Compile into FinalBrief Pydantic object
            
            Edges:
                - START → "content_assembler"
                - "content_assembler" → "completeness_check"
                - "completeness_check" → conditional:
                    - "complete" → "tone_formatter"
                    - "missing_summary" → END (hint: needs summarizer)
                    - "unresolved_critiques" → END (hint: needs critic)
                - "tone_formatter" → "citation_builder"
                - "citation_builder" → "section_writer"
                - "section_writer" → "internal_qa"
                - "internal_qa" → conditional:
                    - "pass" → "brief_finalizer" → END
                    - "fail" → "section_writer" (one retry)
            """

        - _has_unresolved_critiques(self, reports: List[CritiqueReport]) -> bool:
            """Return True if any report has severity 'high' and approved=False"""

    Implementations:
        - _execute_primary_task(state):
            1. Run internal graph
            2. If complete → write FinalBrief to state.final_brief
            3. If incomplete → hint Supervisor for missing dependency
            4. Return updated state

        Note: WriterAgent is the terminal agent. When it successfully writes
        state.final_brief, the Supervisor routes to END.

    Metadata:
        AgentMetadata(
            agent_id="writer_agent",
            capabilities=["write", "compile", "format", "finalize", "output"],
            input_requires=["summary"],
            output_produces=["final_brief"],
            is_terminal=True,
            priority=5
        )
```

**Tools used (imported from `tools/formatting_tools.py`):**
- `FormattingTool.build_citations(findings: List[Finding]) -> List[str]`
- `FormattingTool.apply_tone(text: str, tone: str) -> str`
- `FormattingTool.render_final_brief(brief: FinalBrief) -> str`

---

### `tools/search_tools.py`

**Purpose:** All external data fetching. No LLM logic here — pure I/O.

**Class:** `SearchTool`

```
SearchTool:
    Constructor Args:
        - api_key: Optional[str]        # For real search API (Serper, Tavily, etc.)
        - logger: StructuredLogger

    Methods:
        - search(query: str, max_results: int = 10) -> List[dict]
            """
            Perform a web search and return raw results.
            Implementation: Use Tavily API or DuckDuckGo for real search.
            Each result dict: { "title": str, "url": str, "snippet": str, "score": float }
            
            Falls back to simulated data if api_key is None (for dev/testing).
            """

        - fetch_source_content(url: str, timeout_seconds: int = 10) -> str
            """
            Fetch and extract text content from a URL.
            Use requests + BeautifulSoup for extraction.
            Truncate to 2000 chars to avoid token overflow.
            Raises: SourceFetchError on HTTP errors.
            """

        - simulate_research(topic: str) -> List[dict]
            """
            Return deterministic mock search results for a topic.
            Used in tests and dev mode when no API key is set.
            """
```

---

### `tools/validation_tools.py`

**Class:** `ValidationTool`

```
ValidationTool:
    Methods:
        - check_claim(claim: str, sources: List[str]) -> ClaimCheckResult
            """
            Use LLM (or simple heuristics) to validate if sources support claim.
            ClaimCheckResult: { supported: bool, confidence: float, notes: str }
            """

        - detect_contradictions(findings: List[Finding]) -> List[Contradiction]
            """
            Compare all finding pairs for contradictory statements.
            Use semantic similarity threshold < 0.2 for contradiction detection.
            Contradiction: { finding_a: str, finding_b: str, conflict: str }
            """

        - validate_schema(data: dict, schema_class: Type[BaseModel]) -> ValidationResult
            """
            Validate a dict against a Pydantic schema.
            Returns: { valid: bool, errors: List[str] }
            """
```

---

### `tools/formatting_tools.py`

**Class:** `FormattingTool`

```
FormattingTool:
    Methods:
        - build_citations(findings: List[Finding]) -> List[str]
            """
            Format findings into APA-style citation strings.
            Returns list of citation strings.
            """

        - apply_tone(text: str, tone: str = "professional") -> str
            """
            Post-process text for tone. Tone options: professional, academic, casual.
            Simple rule-based transformations + optional LLM polish.
            """

        - render_final_brief(brief: FinalBrief) -> str
            """
            Convert FinalBrief Pydantic object into formatted markdown string
            for final output display.
            """

        - export_to_json(brief: FinalBrief, filepath: str) -> None
            """Write FinalBrief as JSON to disk"""
```

---

### `utils/cycle_detector.py`

**Class:** `CycleDetector`

```
CycleDetector:
    Static Methods:
        - detect_cycle(call_graph: List[CallEdge], 
                       proposed_caller: str,
                       proposed_callee: str) -> bool
            """
            Check if adding caller→callee edge creates a cycle.
            Algorithm: DFS from proposed_callee, return True if proposed_caller is reachable.
            Time complexity: O(V + E) where V=agents, E=edges
            """

        - get_cycle_path(call_graph: List[CallEdge]) -> Optional[List[str]]
            """
            Return the cycle path as list of agent IDs if cycle exists, else None.
            Example: ["research_agent", "summarizer_agent", "critic_agent", "research_agent"]
            """

        - is_symmetric_call_allowed(call_graph: List[CallEdge], 
                                     caller: str, 
                                     callee: str) -> bool
            """
            Rule 4: A→B and B→A in same session = symmetric call.
            Returns False if B has already called A (unless it's a direct response).
            """
```

---

### `utils/logger.py`

**Class:** `StructuredLogger`

```
StructuredLogger:
    Constructor Args:
        - session_id: str
        - log_level: str

    Methods:
        - log_agent_start(agent_id: str, input_summary: str) -> None
        - log_agent_end(agent_id: str, output_summary: str, duration_ms: float) -> None
        - log_routing_decision(from_agent: str, to_agent: str, reason: str) -> None
        - log_cycle_detected(path: List[str]) -> None
        - log_retry(agent_id: str, retry_count: int, reason: str) -> None
        - log_exhausted(agent_id: str) -> None
        - log_error(agent_id: str, error: Exception) -> None
        - dump_session_log(filepath: str) -> None
            """Write full session log to JSON file"""
```

---

### `utils/retry_manager.py`

**Class:** `RetryManager`

```
RetryManager:
    Constructor Args:
        - max_retries: int
        - max_hops: int

    Methods:
        - can_retry(state: BlackboardState, agent_id: str) -> bool
            """Return True if agent_id has retried < max_retries"""

        - can_continue(state: BlackboardState) -> bool
            """Return True if hop_counter < max_hops"""

        - increment_hop(state: BlackboardState) -> BlackboardState
            """Increment state.hop_counter by 1"""

        - record_retry(state: BlackboardState, agent_id: str) -> BlackboardState
            """Increment state.retry_counts[agent_id]"""
```

---

### `supervisor/supervisor.py`

**Purpose:** The central routing node. Reads blackboard, queries registry, decides next agent.

**Class:** `SupervisorNode`

```
SupervisorNode:
    Constructor Args:
        - registry: AgentRegistry           # Injected singleton
        - cycle_detector: CycleDetector     # Injected utility
        - retry_manager: RetryManager       # Injected utility
        - llm: BaseChatModel                # LLM for ambiguous routing decisions
        - logger: StructuredLogger

    Methods:
        - route(state: BlackboardState) -> str
            """
            Main routing method — this is the LangGraph conditional edge function.
            
            Algorithm:
                1. Check hop_counter >= max_hops → return "__end__"
                2. Check cycle_detected flag → return "__end__"
                3. Read agent hint from state.supervisor_decision
                4. Validate hint against registry
                5. Check cycle_detector.detect_cycle() for proposed route
                6. Check retry_manager.can_retry() for proposed agent
                7. If hint valid and no issues → return agent_id
                8. If hint invalid → call _fallback_routing(state)
                9. Update state.call_graph with routing edge
                10. Log routing decision
            
            Returns: agent_id string for LangGraph to route to, or "__end__"
            """

        - _fallback_routing(self, state: BlackboardState) -> str
            """
            Called when agent hint is missing or invalid.
            
            Logic:
                1. Check what's already on blackboard (raw_findings? summary? critique?)
                2. Derive next logical step from blackboard state completeness
                3. If nothing on blackboard → "clarifier_agent"
                4. If only refined_query → "research_agent"
                5. If raw_findings but no summary → "summarizer_agent"
                6. If summary but no critique → "critic_agent"
                7. If critique resolved → "writer_agent"
                8. If final_brief → "__end__"
            """

        - _llm_routing(self, state: BlackboardState) -> str
            """
            Last resort: ask LLM to decide routing based on current blackboard state.
            Build a JSON prompt: {current_state_summary, available_agents, constraints}
            Parse response for agent_id.
            Only called if _fallback_routing returns ambiguous result.
            """

        - get_node_function(self) -> Callable
            """Return lambda state: self.route(state) for LangGraph edge"""
```

---

### `graph/main_graph.py`

**Purpose:** Assembles the complete LangGraph StateGraph.

**Class:** `MainGraph`

```
MainGraph:
    Constructor Args:
        - supervisor: SupervisorNode
        - registry: AgentRegistry
        - settings: Settings

    Methods:
        - build(self) -> CompiledGraph
            """
            Build and compile the full LangGraph StateGraph.
            
            Steps:
                1. Create StateGraph(BlackboardState)
                2. Add supervisor as the routing node:
                   graph.add_node("supervisor", supervisor.get_node_function())
                3. For each agent in registry.list_all():
                   graph.add_node(agent.agent_id, agent.get_node_function())
                4. Set entry point: graph.set_entry_point("supervisor")
                5. Add conditional edges FROM supervisor:
                   graph.add_conditional_edges(
                       "supervisor",
                       supervisor.route,
                       {
                           "research_agent": "research_agent",
                           "clarifier_agent": "clarifier_agent",
                           "summarizer_agent": "summarizer_agent",
                           "critic_agent": "critic_agent",
                           "writer_agent": "writer_agent",
                           "__end__": END
                       }
                   )
                6. Add return edges FROM each agent BACK to supervisor:
                   for agent_id in all_agent_ids:
                       graph.add_edge(agent_id, "supervisor")
                7. Compile with recursion_limit=settings.langgraph_recursion_limit
                8. Return compiled graph
            """

        - visualize(self, filepath: str = "graph.png") -> None
            """Export LangGraph visualization to PNG using graph.get_graph().draw_mermaid_png()"""
```

---

## 🔁 Execution Flow Example

```
User Input: "Tell me about quantum computing"
     │
     ▼
MainGraph invoked with initial BlackboardState
     │
     ▼
[supervisor] ← No hint yet → _fallback_routing → "clarifier_agent"
     │
     ▼
[clarifier_agent] → Refines topic → writes refined_query → hints "research_agent"
     │
     ▼
[supervisor] ← Reads hint → validates → routes to "research_agent"
     │
     ▼
[research_agent] → Searches → writes raw_findings → hints "summarizer_agent"
     │
     ▼
[supervisor] → routes to "summarizer_agent"
     │
     ▼
[summarizer_agent] → Summarizes → writes summary → hints "critic_agent"
     │
     ▼
[supervisor] → routes to "critic_agent"
     │
     ▼
[critic_agent] → Reviews → approved → hints "writer_agent"
     │
     ▼
[supervisor] → routes to "writer_agent"
     │
     ▼
[writer_agent] → Compiles brief → writes final_brief → no more hints
     │
     ▼
[supervisor] → Reads final_brief present → routes to "__end__"
     │
     ▼
Output: FinalBrief delivered to user
```

---

## 🧩 SOLID Principles Mapping

| Principle | Where Applied |
|-----------|--------------|
| **S** — Single Responsibility | Each agent has one role; registry only stores; supervisor only routes; tools only do I/O |
| **O** — Open/Closed | New agents can be registered without changing supervisor or graph code |
| **L** — Liskov Substitution | Any `BaseAgent` subclass can replace another in the registry |
| **I** — Interface Segregation | `BaseAgent` only requires methods relevant to an agent; tool classes are separate |
| **D** — Dependency Inversion | Agents receive LLM, tools, logger via constructor injection; not instantiated internally |

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
Entry point for Pattern 1: Supervisor + Agent Registry.

Initializes all components, registers agents, builds the graph,
and runs a research query through the full pipeline.
"""

# 1. Load settings
# 2. Initialize StructuredLogger
# 3. Initialize LLM
# 4. Initialize tools (SearchTool, ValidationTool, FormattingTool)
# 5. Initialize AgentRegistry singleton
# 6. Instantiate each agent (inject LLM + tools + logger)
# 7. Register each agent with metadata into registry
# 8. Initialize SupervisorNode (inject registry + utilities + LLM)
# 9. Build MainGraph
# 10. Create initial BlackboardState with topic
# 11. Invoke compiled graph
# 12. Print state.final_brief
```

---

## ✅ Key Design Decisions Summary

- **Registry as Singleton:** Ensures one authoritative source of agent capabilities across the application lifecycle.
- **Supervisor reads blackboard hints:** Agents don't call each other directly — they write routing intentions to the blackboard, and the Supervisor acts on them. This preserves decoupling.
- **Each agent owns its internal graph:** Internal complexity (recursion, sub-steps) is encapsulated inside each agent class. The main graph only sees one node per agent.
- **Cycle detection is pre-routing:** The Supervisor checks for cycles **before** making the routing call, not after.
- **Terminal agents still hint:** Even `WriterAgent` writes to the blackboard. If final_brief is present, the Supervisor routes to `__end__`.
