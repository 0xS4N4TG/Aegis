# Aegis - A LLM Red Team Platform

A terminal-based interface (TUI) based on Textual for testing and evaluating the safety of Large Language Models (LLMs) like Gemini. This tool allows security researchers to identify vulnerabilities through manual and automated adversarial attacks.

## Features

- **Dashboard**: Real-time statistics on attack success rates and jailbreak scores.
- **Attack Library**: Comprehensive catalog of jailbreak techniques (Persona, Logic, Encoding, etc.).
- **Auto-Iterative Attack (PAIR-Lite)**: Automated loop where an "Attacker" model refines prompts to bypass the "Target" model's defenses.
- **Results & Reporting**: Detailed logs of all attempts with export options (Markdown, CSV, JSON).
- **Multi-Model Support**: Switch between different Gemini models (Flash, Pro, etc.) on the fly.

## Attack Techniques

The platform supports **12+ categories** and **47+ techniques**, including:

- **Persona**: Forces the model to adopt an unrestricted persona (e.g., DAN, AIM, Maximum, STAN).
- **Roleplay**: Complex scenarios like "Developer Mode" or "Grandma Exploit" to bypass filters.
- **Logic**: Exploits logical fallacies and Socratic questioning (e.g., Fallacy Failure, Double Bind).
- **Encoding**: Obfuscates prompts using Base64, Rot13, or Morse code to evade keyword detection.
- **Injection**: Classic SQL/Shell injection patterns and payload splitting.
- **Privilege Escalation**: Simulates "Root" or "Admin" commands (e.g., Sudo Mode).
- **Multi-Turn**: Tactics that require building context over multiple messages (e.g., Trust Building).
- **Advanced**:
  - **Recursive Hijacking**: Embedding prompts within layers of instructions.
  - **Prompt Leakage**: Attempts to extract the system instructions.
  - **Toxicity**: Flooding the model with toxic context to break alignment.

## Prerequisites

- Python 3.10 or higher
- A Google AI Studio API Key

## Installation

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and add your API key:
   ```ini
   GEMINI_API_KEY=your_actual_api_key_here
   GEMINI_MODEL=gemini-2.5-flash
   ```

## Usage

Run the application:
```bash
python3 run.py
```

### Controls

- **d**: Dashboard
- **a**: Attack Interface (Manual & Batch)
- **u**: Auto-Attack (Iterative Optimization)
- **r**: Results Table
- **c**: Attack Catalog
- **e**: Export Reports
- **q**: Quit

## Disclaimer

This tool is for educational and defensive security research purposes only. Do not use this tool to attack systems you do not own or have explicit permission to test.
