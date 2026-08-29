# Agentic Shopping System — PRD

Version: 0.1 — MVP
Status: Draft
Product Type: Multi-Agent AI Shopping Experience
Primary Stack: LangChain + LangGraph + React/Next.js

---

## 1. Product Vision

Build a shopping experience where the user does not navigate a traditional ecommerce website.
Instead, the user interacts with a Shopping Agent that understands their intent, performs shopping tasks through specialized agents and tools, and dynamically generates the UI required for the current task.

The UI is therefore not a fixed website.
The Agent decides what the user should see and what actions should be available.

Traditional Ecommerce:

```
User → Website → Search → Filters → Product Page → Compare → Cart
```

Agentic Ecommerce:

```
User → Shopping Agent → Understand intent → Plan → Use tools / delegate to agents
     → Generate appropriate UI → User interacts → Agent observes interaction
     → Continue / change UI / execute action
```

## 2. Problem

Traditional ecommerce interfaces expose users to a large amount of functionality regardless of their current intent.

A user looking for headphones may need to:

- Search
- Filter
- Open product pages
- Read specifications
- Read reviews
- Compare products
- Decide which attributes matter
- Add a product to cart

The system should instead allow the user to express their goal naturally:

> "I need headphones for long flights, under $200. Noise cancellation and comfort are the most important things."

The system should determine the steps required to accomplish this goal.

## 3. Product Goals

Primary Goals

1. Build a functional multi-agent shopping system.
2. Use LangGraph to orchestrate agents and shared state.
3. Allow specialized agents to perform different shopping responsibilities.
4. Allow the system to dynamically generate UI.
5. Make UI interactions first-class inputs to the agent.
6. Demonstrate an end-to-end agent → UI → user → agent loop.

Secondary Goals

- Stream agent execution to the frontend.
- Maintain conversation and shopping state.
- Support product search, filtering, comparison and recommendations.
- Create a reusable UI component registry.
- Keep the UI layer independent from the agent implementation.

## 4. Non-Goals — MVP

The MVP will NOT attempt to build a production ecommerce platform. Specifically:

- No real payments.
- No real checkout.
- No inventory management.
- No shipping infrastructure.
- No large-scale product ingestion.
- No fully autonomous purchasing.
- No arbitrary code generation by the LLM.
- No LLM-generated React/HTML execution.

The initial product will use a controlled/fake product catalog.

## 5. Target User

The initial target user is a consumer who wants to discover and evaluate products without manually navigating a traditional ecommerce website.

Example user:

> "Find me a laptop under 50,000 EGP for frontend development."

The system should progressively help the user reach a purchase decision.

## 6. Core User Experience

### Example Scenario

User:

> "I need headphones for long flights under $200."

### Step 1 — Intent Understanding

The Orchestrator identifies:

- Category: Headphones
- Budget: $200
- Use case: Long flights

It determines that more information may be useful.

The UI Agent generates:

```
┌──────────────────────────────────┐
│ What matters most?               │
│                                  │
│ [ Noise Cancellation ]           │
│ [ Comfort ]                      │
│ [ Battery Life ]                 │
│ [ Sound Quality ]                │
└──────────────────────────────────┘
```

### Step 2 — User Interaction

User selects: Noise Cancellation

The frontend sends an event to the agent.

```json
{
  "type": "ui_action",
  "action": "select_preference",
  "value": "noise_cancellation"
}
```

### Step 3 — Agent Execution

The system searches the product catalog.

```
Orchestrator → Search Agent → Product Research Agent → Recommendation Agent
```

### Step 4 — Dynamic UI

The UI Agent determines that a product grid is appropriate.

```
┌───────────────────────────────────────────┐
│ Best matches for your trip                │
│                                           │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│ │ Product │ │ Product │ │ Product │       │
│ │         │ │         │ │         │       │
│ │ $179    │ │ $199    │ │ $149    │       │
│ │         │ │         │ │         │       │
│ │[Compare]│ │[Compare]│ │[Compare]│       │
│ └─────────┘ └─────────┘ └─────────┘       │
└───────────────────────────────────────────┘
```

### Step 5 — Comparison

User:

> "Compare the first two."

The agent receives the action and changes the UI.

```
┌────────────────────────────────────────────┐
│ Compare                                    │
│                                            │
│                 Product A    Product B     │
│ Price             $179         $199        │
│ Battery           30h          40h         │
│ ANC               ⭐⭐⭐⭐⭐      ⭐⭐⭐⭐      │
│ Comfort           ⭐⭐⭐⭐       ⭐⭐⭐⭐⭐     │
│                                            │
│             [Choose Product B]             │
└────────────────────────────────────────────┘
```

## 7. System Architecture

```
                         USER
                           │
                           ▼
                  ┌─────────────────┐
                  │    Frontend     │
                  │ React / Next.js │
                  └────────┬────────┘
                           │
                     User / UI Events
                           │
                           ▼
                  ┌─────────────────┐
                  │    LangGraph    │
                  │  Orchestrator   │
                  └────────┬────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
    Search Agent    Research Agent   Recommendation Agent
          │                │                │
          └────────────────┼────────────────┘
                           │
                           ▼
                       UI Agent
                           │
                           ▼
                       UI DSL
                           │
                           ▼
                  Component Registry
                           │
                           ▼
                     React Renderer
                           │
                           ▼
                      Dynamic UI
```

## 8. Multi-Agent Architecture

### 8.1 Orchestrator Agent

Responsibility: The Orchestrator is responsible for understanding the user's goal and deciding what should happen next.

Responsibilities:

- Interpret user intent.
- Maintain high-level workflow.
- Delegate tasks.
- Decide when additional information is required.
- Decide when the workflow is complete.
- Coordinate specialized agents.

Example:

> "Find a laptop under 50k for frontend development."

Orchestrator:

→ Search products
→ Research relevant products
→ Ask about priorities if necessary
→ Generate recommendation
→ Ask UI Agent to present results

## 9. Search Agent

Responsibility: Find candidate products matching explicit constraints.

Tools:

- search_products
- filter_products
- search_by_category
- search_by_price
- search_by_attribute

Input:

```json
{
  "category": "laptop",
  "max_price": 50000,
  "use_case": "frontend development"
}
```

Output: Structured product candidates.

## 10. Product Research Agent

Responsibility: Understand product details and extract relevant information.

Tools:

- get_product
- get_product_specs
- get_product_reviews
- compare_product_specs

Example input: Product IDs: [p1, p2, p3]

Output:

- specifications
- relevant attributes
- review summaries
- potential advantages/disadvantages

## 11. Recommendation Agent

Responsibility: Rank and explain products based on the user's preferences.

Example — user priorities:

```
Battery: 0.5
Display: 0.3
Performance: 0.2
```

Output:

```json
{
  "recommended_product": "p17",
  "alternatives": ["p12", "p31"],
  "reasoning": [
    "Best battery life",
    "Excellent display",
    "Meets budget"
  ]
}
```

The recommendation agent should produce structured reasoning suitable for presentation, rather than exposing hidden chain-of-thought.

## 12. UI Agent

Most Important Agent in the MVP.

The UI Agent converts the current shopping state and user intent into a structured UI description.
It does NOT generate React code.

Example input: User wants to compare three products.

Output:

```json
{
  "type": "page",
  "children": [
    {
      "type": "comparison_table",
      "props": { "productIds": ["p1", "p2", "p3"] }
    },
    {
      "type": "recommendation_card",
      "props": { "productId": "p2" }
    }
  ]
}
```

The frontend renderer converts this into actual React components.

## 13. UI Component Registry

The MVP will have a controlled set of components.

Core Components:

Text, Button, Card, ProductCard, ProductGrid, ProductDetails, ComparisonTable, SearchInput, Select, CheckboxGroup, PriceRange, FilterPanel, RecommendationCard, Modal, LoadingState, ErrorState

Each component has:

- Schema
- Props
- Allowed actions
- Validation rules
- Renderer

## 14. UI DSL

The UI DSL is the contract between the Agent and Frontend.

Example:

```json
{
  "type": "product_grid",
  "props": {
    "title": "Best matches",
    "productIds": ["p1", "p2", "p3"]
  },
  "actions": [
    { "type": "compare", "label": "Compare" }
  ]
}
```

Important Rule: The LLM can select and configure components.
It cannot execute arbitrary frontend code.

```
LLM → Structured UI Schema → Validation → Component Registry → React
```

## 15. Agent State

The LangGraph shared state will contain the information required across the shopping workflow.

Initial conceptual state:

```ts
type ShoppingState = {
  messages: Message[];

  userIntent: {
    category?: string;
    budget?: number;
    preferences?: Record<string, unknown>;
    useCase?: string;
  };

  products: Product[];
  selectedProducts: string[];
  research?: ProductResearch[];
  recommendation?: Recommendation;
  ui?: UIPlan;
  currentAgent?: string;
  pendingAction?: UIAction;
};
```

The exact schema will be refined during implementation.

## 16. Agent Workflow

The initial LangGraph workflow:

```
START
  ↓
Orchestrator
  ↓
Need Information?
  ├── YES → UI Agent → User → User Action → Orchestrator
  └── NO
       ↓
    Search → Research → Recommendation → UI Agent → END
```

Later versions can introduce more dynamic routing.

## 17. Tools

Tools should be explicit and strongly typed.

Product Tools:

- search_products()
- get_product()
- get_product_specs()
- get_product_reviews()
- compare_products()

Shopping Tools:

- add_to_cart()
- remove_from_cart()
- get_cart()

User Preference Tools:

- save_preference()
- get_preferences()

The MVP can implement these against a local data source.

## 18. Frontend ↔ Agent Protocol

The frontend communicates with the agent through two primary message types.

Agent → Frontend:

```json
{ "type": "ui_update", "ui": {} }
```

Frontend → Agent:

```json
{
  "type": "ui_action",
  "action": "compare",
  "payload": { "productIds": ["p1", "p2"] }
}
```

Other events:

- user_message
- ui_action
- selection_change
- form_submit
- cancel

## 19. Streaming

The system should support streaming agent execution.

Example:

```
Agent started → Searching products... → Found 24 products
→ Analyzing top candidates... → Building recommendations...
→ Generating UI... → UI ready
```

The frontend can optionally expose lightweight execution status to the user.

## 20. MVP User Capabilities

The user should be able to:

- Search: "Find me headphones under $200."
- Refine: "Only show ones with more than 30 hours of battery."
- Ask Questions: "Which one is best for long flights?"
- Compare: "Compare the first two."
- Inspect: "Show me more details about this one."
- Add to Cart: "Add this to my cart."
- Change Priorities: "I care more about comfort than sound quality."
- Continue Conversation: The system should maintain context throughout the session.

## 21. Example End-to-End Flow

```
User: "Find headphones under $200 for long flights"
  → Orchestrator (extract intent)
  → Search Agent (search_products())
  → Product Research Agent (get_product_specs(), get_product_reviews())
  → Recommendation Agent (rank products)
  → UI Agent (generate ProductGrid)
  → Frontend (render UI)
  → User clicks Compare → Agent Event → Orchestrator → Comparison UI
```

## 22. Success Criteria

Agent:

- Multiple specialized agents work together.
- The Orchestrator can route tasks.
- Agents communicate through shared LangGraph state.
- Tools are invoked correctly.
- The workflow can react to user interactions.

UI:

- UI is generated dynamically.
- UI is driven by structured schemas.
- The frontend never executes arbitrary LLM-generated code.
- User interactions can trigger new agent decisions.
- The agent can replace or augment the current UI.

Experience — a user can complete this flow entirely through the agent:

Search → Refine → Inspect → Compare → Get recommendation → Add to cart
without navigating traditional ecommerce pages.

## 23. MVP Technical Constraints

Agent Framework:

- LangChain
- LangGraph
- Typed tool interfaces
- Structured outputs

Frontend:

- Next.js
- React
- TypeScript
- Dynamic component renderer

Data:

- Initially: Local Product Dataset → Product Tools → Agents
- No external ecommerce integration is required for MVP.

## 24. Future Direction

After the MVP works, the system can evolve toward:

Real Shopping — connect real product APIs and merchants.

More Specialized Agents: Price Agent, Review Agent, Deal Agent, Inventory Agent, Shipping Agent, Cart Agent, Checkout Agent.

Autonomous Shopping — the agent could eventually execute a complete shopping workflow:

Understand need → Research → Compare → Recommend → Ask approval → Purchase
with explicit user authorization before irreversible actions.

Agent-Generated Experiences — the long-term goal is for the agent to construct a personalized shopping experience rather than simply populate a predefined ecommerce page.

## 25. Product Principle

The central principle of the product is:

> The UI is an output of the agent, not the place where the agent operates.

Traditional: UI → User → Actions
Agentic: User → Agent → UI → User → Agent → UI

The UI becomes a dynamic communication and interaction layer between the user and the agent.

## 26. MVP Definition

The first working version should demonstrate exactly one strong scenario:

> "Help me find the best headphones for long flights under $200."

The system must:

1. Understand the request.
2. Search products.
3. Research candidates.
4. Rank candidates.
5. Generate a dynamic product UI.
6. Accept UI interactions.
7. Re-enter the agent loop.
8. Generate a comparison UI.
9. Explain the recommendation.
10. Add the selected product to a mock cart.

If this flow works reliably, the underlying architecture can then be generalized to other shopping categories.
