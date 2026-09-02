<p align="center">
  <img src="docs/screenshots/logo_v3.png" alt="PRISM Logo" width="380" />
</p>

<p align="center">
  <a href="https://github.com/zhaopeizhao41-ops/PRISM"><img src="https://img.shields.io/badge/PRISM-v0.2.0-FF4D00?style=for-the-badge&logo=target&logoColor=white" alt="PRISM Version" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-111111?style=for-the-badge&logo=python&logoColor=white" alt="Python Version" /></a>
  <a href="https://vuejs.org/"><img src="https://img.shields.io/badge/Vue-3.x%20%2B%20Vite-42B883?style=for-the-badge&logo=vuedotjs&logoColor=white" alt="Vue 3" /></a>
  <a href="https://github.com/zhaopeizhao41-ops/PRISM/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0-111111?style=for-the-badge" alt="License" /></a>
  <img src="https://img.shields.io/badge/Tests-129%20Passed-057A55?style=for-the-badge&logo=pytest&logoColor=white" alt="Tests" />
  <img src="https://img.shields.io/badge/Multimodal-Vision%20Ready-6C2BD9?style=for-the-badge&logo=openai&logoColor=white" alt="Multimodal" />
</p>

<p align="center">
  <b>A beam of light passes through a prism, refracting into countless paths. So does your life.</b><br>
  <b>The universe is full of chaos, yet we always have a choice.</b><br>
  <i>A personal reality simulation & multi-universe decision laboratory constrained by causal laws and reality ledgers.</i>
</p>

<p align="center">
  <a href="#creation-story--philosophy">Philosophy</a> •
  <a href="#core-pipeline">Core Pipeline</a> •
  <a href="#key-features">Key Features</a> •
  <a href="#multi-format-ingestion">Data Ingestion</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="README-ZH.md">中文说明</a>
</p>

---

## Creation Story & Philosophy

> *“We built PRISM from an intensely personal moment. My close friend and I were standing at a defining crossroad in life, feeling something quiet yet suffocating—**chaos**. The future was a dense fog without outlines or depth. We were not lacking options; we were trapped by their invisibility: not knowing where the doors were, not knowing the true costs of each step, and unaware of how far we could actually reach.*
>
> *So we wrote the first line of code. Not to forecast the future—no one can. But to **let you see how vast a possibility space can unfold from who you are right now**.”*

**PRISM does not dictate how you should live.** It does something far more honest and empowering:  
It takes your authentic coordinates—your skills, resources, constraints, fears, and ties—and feeds them into a multi-agent simulation engine to unfold uncollapsed possibilities. Every path is marked with its true costs and potential returns—no glossing over, no cheap optimism.

- 🔬 **Simulation, Not Divination**: Grounded in your verifiable personal baseline and causal dynamics, every trajectory is traceable, quantifiable, and open to question.
- 🌌 **Chaos Is Not the End; Choice Is**: Uncertainty never equals helplessness. At every fork, you possess **real, autonomous choices**. Confusion does not stem from a lack of paths, but from not having seen them yet.
- 🪞 **You Are Broader Than You Imagine**: Most people underestimate the sheer area of their possibility space because present anxiety compresses their vision. From the exact coordinate where you stand, the refracted possibilities reach far beyond imagination.

---

## Core Pipeline

<p align="center">
  <img src="docs/screenshots/architecture_pipeline.png" alt="PRISM Pipeline Diagram" width="100%" />
</p>

```
Real Coordinates (Word / Excel / PPT / PDF / Chat Logs / Diary Photos)
        │
        ▼
Personal Knowledge Graph      (Zep Cloud GraphRAG, Fixed Ontology)
        │
        ▼
Personal Model Synthesis       (3-Stage LLM Synthesis, Versioned + Hash-Stamped)
        │
        ├──► 01. Life Branches       (5 Archetype-Driven Parallel Trajectories)
        │         │
        │         ▼
        │    02. Deep Evolution      (Stage-by-Stage Advance + Realism Ledger)
        │         │
        │         ▼
        │    03. Multi-Universe      (Side-by-Side 4D Matrix Comparison)
        │         │
        │         ▼
        │    04. Roundtable Debate   (Multi-Round Cross-Auditing & Letta Memory)
        │         ▼
        │    Many Possible Lives     (Not to Foresee the Future, But to Explore Possibility)
        │
        └──► 05. Graph Observatory   (Interactive D3.js Force-Directed Graph)
```

---

## Product Showcase

| 01. Personal Profile & Grounded Ledger | 02. Archetype Life Branch Refraction |
|:---:|:---:|
| ![Personal Profile](docs/screenshots/profile.png) | ![Life Branches](docs/screenshots/branches.png) |

| 03. Multi-Universe Deep Evolution State Machine | 04. Multi-Round Roundtable & Cross-Auditing |
|:---:|:---:|
| ![Deep Evolution](docs/screenshots/evolution.png) | ![Roundtable](docs/screenshots/roundtable.png) |

---

<a name="multi-format-ingestion"></a>
## Multi-Format Data Ingestion Matrix

PRISM supports zero-friction ingestion across 17+ everyday personal document and media formats:

| Category | Formats | Processing Engine | Key Capabilities |
| :--- | :--- | :--- | :--- |
| **Office Documents** | `.docx`, `.doc`, `.pdf` | `python-docx`, `PyMuPDF` | Parses resumes, essays, reflection notes, and embedded experience tables locally in milliseconds. |
| **Spreadsheets & Data** | `.xlsx`, `.xls`, `.csv` | `openpyxl`, `csv` | Extracts financial runways, expense streams, and life timeline logs into structured text matrices. |
| **Presentations** | `.pptx` | `python-pptx` | Extracts slide body text, roadmap outlines, and speaker notes. |
| **Chats & Web Exports** | `.html`, `.json`, `.txt`, `.log`, `.rtf` | `BeautifulSoup4`, multi-encoding detector | Strips HTML formatting, parses exported WeChat/QQ message lists, and ingests Notion/Feishu export packs. |
| **Images & Screenshots** | `.png`, `.jpg`, `.jpeg`, `.webp` | Vision Multimodal LLM (`deepseek-v4-flash-vision-exp`, `qwen-vl`, `gpt-4o`) | High-fidelity OCR and semantic extraction from chat screenshots, handwritten diaries, and report cards. |

---

## Key Features

- **Multi-Modal Personal Model Synthesis**: Combines structured quantitative surveys and unstructured private materials (diaries, resumes, essays, chat logs) with source-weighted confidence scoring into versioned, hash-stamped personal models.
- **Character-LLM Episodic Anchors & Psychological Defense Axis**: Extracts real-life memory anchors and defense patterns to prevent character collapse and maintain personality fidelity.
- **Mem0 Atomic Memory Mutation Pipeline**: Incrementally updates agent memories with structured `ADD`, `UPDATE`, `DELETE`, and `NOOP` atomic operations across evolutionary stages.
- **Letta / MemGPT Hierarchical Working Memory**: Maintains 3-block core working context (`persona`, `human`, `situation`) with autonomous agent self-editing routines during roundtables.
- **AI Town Deterministic 0-Token Realism Circuit Breaker**: Hard-constrained physical ledgers (cash runway, social tension, physical health, psychological resilience) that halt hallucinations without wasting LLM tokens.
- **AgentVerse Stakeholder Autonomous Agency & Pressure Mechanics**: Simulates dynamic resistance, pressure games, and boundary testing from key relationships (parents, partners, investors).
- **Multi-Round Roundtable Debate Engine (1-4 Rounds)**: Conducts multi-round cross-examination, rebuttal, and consensus convergence among parallel selves and stakeholders with clean neo-brutalist round dividers.
- **Impartial Moderator Epistemic Audit**: Quantitative convergence index, inevitable survival constraints, high-leverage decision variables, and 1-page markdown decision memo export.
- **Anti-Drift Fidelity Guard**: Real-time evaluation of stage evolution and speech consistency against baseline personal models and expression DNA.
- **Neo-Brutalist Paper Instrument UI**: Crisp typography, high-contrast visual tokens, physical hover lift and active press feedback, zero emojis, and complete internationalization (EN/ZH).

---

## Tech Stack

| Layer | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | Vue 3 + Vite | Single Page Application with Vue Router & Pinia |
| **Visualization** | D3.js | Interactive force-directed ontology graph |
| **Backend** | Python 3.11+ / Flask | High-throughput REST API |
| **Simulation Engines** | Stanford GA + Letta + Mem0 | Multi-agent cognitive memory & reflection |
| **Knowledge Graph** | Zep Cloud | GraphRAG memory backend with fixed ontology |
| **LLM Inference** | OpenAI Compatible | Tested with `deepseek-v4-flash-vision-exp`, `qwen-plus`, `gpt-4o` |
| **Storage** | Structured Local JSON | Zero-DB file storage under `uploads/projects/` |

---

## Getting Started

### Prerequisites

- **Node.js**: $\ge 18.0.0$
- **Python**: $\ge 3.11, \le 3.12$
- **uv**: Fast Python package manager ([Installation Guide](https://docs.astral.sh/uv/))
- **Zep Cloud API Key**: [Zep Cloud Console](https://app.getzep.com/)
- **LLM API Key**: OpenAI-compatible API key (e.g. DeepSeek, DashScope Qwen, OpenAI)

### 1. Clone Repository

```bash
git clone https://github.com/zhaopeizhao41-ops/PRISM.git
cd PRISM
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
# LLM Configuration (OpenAI-compatible)
LLM_API_KEY=your_llm_api_key_here
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL_NAME=deepseek-v4-flash-vision-exp

# Zep Cloud GraphRAG Configuration
ZEP_API_KEY=your_zep_api_key_here

# Backend Service
PORT=5001
DEBUG=True
```

### 3. Install Dependencies

Install all frontend and backend dependencies in one step:

```bash
npm run setup:all
```

### 4. Start Development Servers

Run both backend and frontend concurrently:

```bash
npm run dev
```

- **Frontend Application**: [http://localhost:3000](http://localhost:3000)
- **Backend REST API**: [http://localhost:5001](http://localhost:5001)

---

## Documentation in Chinese

For complete Chinese documentation, design philosophy, and guides, please visit [README-ZH.md](README-ZH.md).

---

## License

This project is licensed under the [AGPL-3.0 License](LICENSE).
