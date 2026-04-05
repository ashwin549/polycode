# Polycode

A Claude Code-style coding agent that works with any LLM — Claude, GPT, Gemini, or local Ollama models.

---

## Features

- Multi-provider — swap models with a single flag  
- File tools — read, write, list files in your project  
- Diff-based editing — targeted `str_replace` edits with approval prompts  
- Web search — DuckDuckGo, no API key required  
- Isolated shell — Docker-sandboxed command execution (read-only workspace mount, no network)  
- Persistent history — conversation history stored per session  

---

## Setup (Step-by-step)

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd polycode
```

---

### 2. Install dependencies

Make sure you are inside the project directory:

```bash
pip install -e .
```

If you are using a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate   # Linux / macOS
venv\Scripts\activate      # Windows

pip install -e .
```

---

### 3. Configure API keys

Create a `.env` file in the root of the project:

```
polycode/
├── .env
├── polycode/
├── setup.py
...
```

Add your API keys in the following format:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
```

Only include the keys for providers you plan to use.

---

### 4. Add Polycode to system PATH (Windows)

So you can run `polycode` from anywhere:

1. Press `Win + S` → search Environment Variables  
2. Click Edit the system environment variables  
3. Click Environment Variables  
4. Under User variables, select `Path` → click Edit  
5. Click New and add the full path to your project directory (where `polycode` is installed)  
6. Click OK on all dialogs  

Restart your terminal after this.

---

### 5. Run Polycode

Navigate to any project directory where you want to use the agent:

```bash
cd your-project-folder
polycode
```

---

## Usage

### Default (Claude)

```bash
polycode
```

### OpenAI

```bash
polycode --provider openai
```

### Gemini

```bash
polycode --provider gemini
```

### Ollama (local models)

```bash
polycode --provider ollama
polycode --provider ollama --model mistral
```

---

## Switching providers (optional)

You can set a default provider using environment variables:

```bash
export POLYCODE_PROVIDER=gemini   # Linux/macOS
setx POLYCODE_PROVIDER gemini     # Windows
```

Then simply run:

```bash
polycode
```

---

## Commands

| Command  | Description |
|----------|-------------|
| `/help`  | Show available commands |
| `/clear` | Clear conversation history |
| `/cwd`   | Show working directory |
| `/quit`  | Exit |

---

## Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read a file with line numbers |
| `write_file` | Write or create a file |
| `list_files` | List directory contents |
| `edit_file` | Targeted `str_replace` edit with diff preview |
| `web_search` | DuckDuckGo search |
| `shell` | Run commands in a Docker container |

---

## Shell isolation

The shell tool requires Docker.
Install Docker Desktop and run it. 
Make sure the image is pulled by running (you only need to do this once):

```bash
docker pull python:3.12-slim
```


Commands run inside a `python:3.12-slim` container with:

- Your working directory mounted read-only at `/workspace`
- A temporary directory mounted read-write at `/output`
- No network access
- 512 MB memory limit
- 0.5 CPU limit
- 60-second timeout

If Docker is not available, the shell tool will report it and skip execution.

---

## Architecture

```
polycode/
├── providers/          # LLM adapters (normalized to a common interface)
│   ├── base.py
│   ├── anthropic_provider.py
│   ├── openai_provider.py
│   ├── gemini_provider.py
│   └── ollama_provider.py
├── tools/              # Agent capabilities
│   ├── file_tools.py
│   ├── edit_tools.py
│   ├── search_tools.py
│   └── shell_tools.py
├── agent.py            # Tool-use loop
└── cli.py              # REPL interface
```
