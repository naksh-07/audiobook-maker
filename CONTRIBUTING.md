# 🤝 Contributing to Audiobook Maker

First off, thank you for considering contributing to **Audiobook Maker (Audiobook Factory)**! We appreciate your time and effort to improve this studio-grade pipeline.

## 🛠️ Local Development Setup

To ensure a clean environment, please use a Python virtual environment.

### 1. Clone the repository
```bash
git clone https://github.com/naksh-07/audiobook-maker.git
cd audiobook-maker
```

### 2. Create and Activate Virtual Environment
```bash
# On Linux / macOS / Termux
python3 -m venv .venv
source .venv/bin/activate

# On Windows (if developing on PC)
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies
This project is designed to be **Zero Pip Dependency** for its core features to run effortlessly on mobile environments like Android Termux. 
However, for development and testing, you can install the optional `dev` dependencies.
```bash
pip install -e .[dev]
```

### 4. Setup Environment Variables
```bash
cp .env.example .env
```
Fill in your API keys in the `.env` file for testing. **Never commit your `.env` file.**

## 🧪 Running Tests

We use `pytest` for unit testing. Make sure your changes do not break existing functionality.

```bash
pytest tests/ -v
```

## 📐 Code Style & Conventions

- **Python Version:** We strictly target Python 3.10+.
- **Standard Library Only:** If you are adding a new core feature, strive to use the Python Standard Library (`urllib`, `json`, `subprocess`, etc.) to maintain the lightweight footprint. Avoid introducing heavy ML libraries directly into the CLI.
- **Type Hinting:** Use standard Python type hinting for all function arguments and return types.
- **Docstrings:** Ensure modules and functions have descriptive docstrings explaining their purpose.

## 🚀 Pull Request Process

1. **Fork** the repository and create your feature branch:
   ```bash
   git checkout -b feature/amazing-feature
   ```
2. **Commit** your changes with clear, descriptive messages:
   ```bash
   git commit -m "feat: Add support for custom soundscape crossfades"
   ```
3. **Push** to your branch:
   ```bash
   git push origin feature/amazing-feature
   ```
4. **Open a Pull Request** against the `main` branch. Provide a detailed description of what you've added or fixed.

## 🐛 Found a Bug?
If you find a bug, please check the [Issue Tracker](https://github.com/naksh-07/audiobook-maker/issues) to see if it has already been reported. If not, open a new issue with a clear title and detailed steps to reproduce.

---

*Thank you for helping us make audiobook production accessible for everyone!*
