# SpecGuard AI

### Specification-Grounded API Test Generation & Quality Assurance

**SpecGuard AI** is an LLM-powered API testing framework that transforms OpenAPI specifications into structured, validated, and executable test cases.

The project combines generative AI, specification-aware validation, HTTP test automation, and quantitative quality assessment to support a more reliable API testing workflow.

Developed as part of a Software Testing with AI academic project.

**Contributors**
- Mariem Mezghani — AI Test Generation & Semantic Validation
- Rimeh Abidi — API Execution Engine & QA Reporting

---

## 1. Overview

Traditional API testing often requires manually interpreting API specifications, designing test scenarios, and writing test scripts.

SpecGuard AI explores how large language models can automate test-case generation while maintaining consistency with documented API behavior.

Unlike a basic LLM test generator, SpecGuard AI introduces a validation layer that detects unsupported assumptions before generated tests are exported for execution.

**Core principle:** Generate with AI, validate against the specification, execute against the API, and evaluate the results.

## 2. Key Features

### AI-Powered Test Generation — Implemented

- OpenAPI 3.x specification parsing (supported features documented in the repository).
- LLM-powered generation of positive, negative, and boundary test scenarios.
- Local LLM inference using Ollama and Qwen2.5-Coder 7B.
- Configurable OpenAI-compatible LLM providers.
- Structured JSON output.
- Prompt versioning and reproducible mock workflows.

### Specification-Aware Validation — Implemented

- Pydantic-based structural validation.
- Semantic consistency checks against OpenAPI.
- Detection of unsupported response assertions.
- Classification of hypothetical scenarios.
- Duplicate detection.
- Export using a shared JSON contract.

### Automated API Execution — Integration Pending

- HTTP request execution from generated test cases.
- Status-code and response-body assertions.
- Positive and negative API testing.
- Execution result collection.
- Reproducible test runs.

### Quality Assessment — Partially Implemented

Generation-side measurements are available, including structural validity, semantic acceptance, operation generation coverage, test distribution, and generation time.

Execution-side measurements and consolidated QA reports will be completed during the integration phase.

## 3. System Architecture

```text
OpenAPI Specification
         |
         v
  OpenAPI Parser
         |
         v
  Prompt Builder
         |
         v
  LLM Test Generator
   (Ollama / Qwen)
         |
         v
 Structural Validator
         |
         v
  Semantic Validator
      /       \
     v         v
Validated   Hypothetical
  Tests      Scenarios
     |
     v
generated_tests.json
     |
     v
  API Test Runner
     |
     v
HTTP Assertions & Metrics
     |
     v
   QA Report
```

The generator and execution engine are developed independently and communicate through a versioned JSON contract.

## 4. Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python |
| Generative AI | Qwen2.5-Coder 7B |
| Local LLM runtime | Ollama |
| LLM integration | OpenAI-compatible API |
| API specifications | OpenAPI / Swagger |
| Data validation | Pydantic |
| API demonstration | FastAPI (integration phase) |
| HTTP test execution | httpx (integration phase) |
| Unit testing | pytest |
| Version control | Git & GitHub |

## 5. Experimental Results

An initial experiment compared two prompt versions using a local Qwen2.5-Coder 7B model.

| Metric | Prompt 1.0.0 | Prompt 1.1.0 |
|---|---:|---:|
| Generated candidates | 6 | 6 |
| Validated tests | 4 | 6 |
| Hypothetical scenarios | 2 | 0 |
| Structural validity | 100% | 100% |
| Semantic acceptance | 66.67% | 100% |
| Operation generation coverage | 100% | 100% |
| Generation time | 26.73 s | 32.97 s |

The revised prompt encouraged partial response assertions and reduced unsupported assumptions in the observed execution.

**Important:** These are exploratory results based on one live generation per prompt version. They are not evidence of statistically significant improvement. Historical generation settings were not fully archived, so strict experimental equivalence cannot be guaranteed.

The generator also passed **145 automated pytest tests** at the last reported validation.

## 6. Getting Started — AI Generator

### Prerequisites

- Python 3.11+
- Ollama (for local inference)
- A compatible local model, such as `qwen2.5-coder:7b`

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/specguard-ai.git
cd specguard-ai
python -m pip install -r requirements.txt
```

### LLM Configuration

Create a `.env` file from `.env.example`.

Example configuration for Ollama:

```env
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5-coder:7b
LLM_TEMPERATURE=0
LLM_TIMEOUT=180
LLM_MAX_RETRIES=2
LLM_RESPONSE_FORMAT=json_object
LLM_MAX_TOKENS=4096
```

Start Ollama if it is not already running:

```bash
ollama serve
```

### Generate API Tests

Reproducible mock mode:

```bash
python -m ai_generator.cli generate --spec examples/sample_openapi.json --output outputs/generated_tests.json --mode mock
```

Live LLM mode:

```bash
python -m ai_generator.cli generate --spec examples/sample_openapi.json --output outputs/generated_tests_ollama.json --mode live
```

### Run Unit Tests

```bash
python -m pytest -q
```

Additional audit and experiment commands are documented in the module-specific documentation.

## 7. Integration Contract

Both modules communicate through `generated_tests.json`, using schema version `1.0`.

Example:

```json
{
  "schema_version": "1.0",
  "tests": [
    {
      "test_id": "TC_001",
      "name": "Get nonexistent product",
      "method": "GET",
      "endpoint": "/products/{id}",
      "test_type": "negative",
      "path_params": {"id": 999999},
      "query_params": {},
      "headers": {},
      "body": null,
      "expected_status": 404,
      "expected_body": null
    }
  ]
}
```

This shared interface allows the LLM generation module and API execution module to evolve independently.

## 8. Project Responsibilities

**Mariem Mezghani — AI Generation Module**

Responsible for OpenAPI parsing, prompt engineering, LLM integration, test generation, semantic validation, JSON export, prompt logging, and generation metrics.

**Rimeh Abidi — API Testing Module**

Responsible for the demonstration API, HTTP test execution, response assertions, execution metrics, and QA reporting.

**Joint work:** Contract compatibility, end-to-end integration, experimental evaluation, final documentation, and demonstration.

## 9. Current Project Status

| Component | Status |
|---|---|
| OpenAPI parser | Implemented |
| LLM-based generation | Implemented |
| Ollama inference | Tested locally |
| Structural and semantic validation | Implemented |
| Prompt comparison | Initial experiment completed |
| JSON integration contract | Established |
| API execution module | Developed separately; integration pending |
| End-to-end execution | Pending |
| Final evaluation | Pending |

## 10. Limitations and Future Work

Current limitations include dependence on OpenAPI documentation quality, uncertainty about actual API data and state, and limited experimental repetitions.

Planned work includes end-to-end execution, evaluation across multiple API specifications, controlled prompt comparisons, and final QA reporting.

---

## Authors

**Mariem Mezghani & Rimeh Abidi**

Academic Project — Software Testing Assisted by Artificial Intelligence

*SpecGuard AI — From API specifications to validated test cases.*
 
