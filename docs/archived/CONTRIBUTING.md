````markdown
# Contributing to Personal Model Development

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the Financial Statement Normalization Engine.

---

## 🎯 Code of Conduct

Please be respectful and professional in all interactions. We welcome contributions from everyone regardless of experience level.

---

## 🐛 Reporting Issues

### Before Reporting
1. Check [PROJECT_REVIEW.md](PROJECT_REVIEW.md) - your question might be answered there
2. Search existing GitHub issues - it might already be reported
3. Review [QUICK_START.md](QUICK_START.md) - common issues are documented there

### How to Report a Bug
1. **Use a clear title** - "Parser fails with missing Amount column" is better than "Bug"
2. **Describe the issue** - What were you trying to do?
3. **Provide steps to reproduce** - How can someone else see the same issue?
4. **Include sample data** - A minimal example file that triggers the bug
5. **Share your environment** - Python version, OS, etc.

### Example Bug Report
```
Title: CSV Parser Error When "Amount" Column Has Spaces

Description:
When my CSV file has the amount column named "Amount ", the parser fails.

Steps to reproduce:
1. Create CSV with column named "Amount " (with trailing space)
2. Run: python src/main.py --input test.csv
3. See error: Column "Amount" not found

Expected: Should auto-trim column names
Actual: Parser crashes

Environment:
- Python 3.12.3
- pandas 2.1.0
- macOS 13
```

---

## 💡 Suggesting Enhancements

### Before Suggesting
1. Check if it already exists in the code
2. Review [PROJECT_REVIEW.md](PROJECT_REVIEW.md) - might be planned
3. Make sure it fits the project scope

### How to Suggest an Enhancement
1. **Clear title** - "Add JSON export format" vs "Add export"
2. **Describe the enhancement** - What problem does it solve?
3. **Provide examples** - Show how it would work
4. **Suggest implementation** - If you have ideas

### Example Enhancement Request
```
Title: Add JSON Export Format

Description:
Currently only CSV output is available. JSON would be useful for API integrations.

Example use case:
python src/main.py --output results/ --format json
Result: Results saved as JSON for API consumption

Implementation notes:
- Create JSONExporter class in src/export/
- Add --format argument to main.py
- Support nested structure for hierarchical data
```

---

## 🔧 Development Setup

### 1. Fork the Repository
Click "Fork" on GitHub to create your own copy

### 2. Clone Your Fork
```bash
git clone https://github.com/YOUR_USERNAME/Personal-Model-Development.git
cd Personal-Model-Development
```

### 3. Create a Development Branch
```bash
# Always work in a feature branch, never on main
git checkout -b feature/your-feature-name
```

### 4. Install in Development Mode
```bash
cd financial-normalizer
pip install -r requirements.txt
pip install -e .  # Install in editable mode if setup.py exists
```

### 5. Make Your Changes
Edit files and test locally

### 6. Run Tests
```bash
# Verify your changes don't break anything
python run_tests.py

# Run specific module tests
python test_imports.py

# Verify setup
python verify_setup.py
```

---

##✍️ Code Style Guidelines

### Python Style
We follow **PEP 8** conventions:

- **Indentation**: 4 spaces
- **Line length**: Max 100 characters
- **Naming**:
  - Classes: `PascalCase` (e.g., `ClassificationEngine`)
  - Functions/variables: `snake_case` (e.g., `classify_account`)
  - Constants: `UPPER_CASE` (e.g., `DEFAULT_TIMEOUT`)

### Example Code Style
```python
"""Module docstring explaining purpose"""

from typing import List, Optional
import pandas as pd
from dataclasses import dataclass


@dataclass
class MyClass:
    """Docstring for the class"""
    name: str
    value: float
    
    def my_method(self, param: str) -> bool:
        """
        Docstring for the method.
        
        Args:
            param: Description of parameter
            
        Returns:
            Description of return value
        """
        # Implementation
        return True


def standalone_function(data: pd.DataFrame) -> pd.DataFrame:
    """Docstring for standalone function"""
    # Implementation
    return data
```

---

## 📝 Commit Guidelines

### Commit Message Format
```
<type>: <subject>

<body>

<footer>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Build, dependencies, etc.

### Examples
```
feat: Add JSON export format

- Create JSONExporter class
- Add --format argument
- Support nested JSON output

Fixes #123
```

```
fix: Handle trailing spaces in CSV column names

When column names have trailing spaces, the parser now
auto-trims them before matching.

Fixes #456
```

---

## 📤 Submitting a Pull Request

### 1. Push Your Changes
```bash
git push origin feature/your-feature-name
```

### 2. Create a Pull Request on GitHub
- Provide a clear title
- Reference any related issues
- Describe what changed and why

### 3. PR Description Template
```markdown
## Description
Brief description of the changes

## Motivation
Why is this change needed?

## Testing
How was this tested?

## Checklist
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] Code follows style guidelines
- [ ] No breaking changes

## Closes
Closes #issue_number
```

### 4. Review Process
- Maintainers will review your PR
- May request changes
- Once approved, will be merged

---

## ✅ What Makes a Good PR

1. **Focused** - Solves one problem, not multiple
2. **Tested** - Includes tests for new code
3. **Documented** - Updates docs if needed
4. **Clean** - Follows code style guidelines
5. **Explained** - Clear description of changes
6. **Referenced** - Links to related issues

---

## 🎓 Project Structure (For Contributors)

### Adding a New Feature

**Example**: Adding PDF export

```
1. Create new file: src/export/pdf_exporter.py
2. Implement PdfExporter class with export() method
3. Update src/export/__init__.py to import it
4. Add --format pdf argument handling in src/main.py
5. Add tests in run_tests.py
6. Update DEVELOPMENT.md with usage docs
7. Test: python run_tests.py
8. Commit and create PR
```

### Adding a New Industry

```
1. Edit config/categories.yaml
2. Add new industry section with:
   - revenue_accounts
   - cogs_accounts
   - operating_expenses
3. Test: python src/main.py --industry your_industry
4. Document in DEVELOPMENT.md
5. Add sample data if possible
```

### Fixing a Bug

```
1. Create a branch: git checkout -b fix/bug-description
2. Write a test that reproduces the bug
3. Fix the code
4. Verify test now passes
5. Run all tests: python run_tests.py
6. Create PR with clear description
```

---

## 🧪 Testing

### Writing Tests
Tests are in [financial-normalizer/run_tests.py](financial-normalizer/run_tests.py)

```python
def test_your_feature():
    """Test description"""
    # Arrange
    input_data = setup_test_data()
    
    # Act
    result = your_function(input_data)
    
    # Assert
    assert result is not None
    assert result['key'] == expected_value
```

### Run Tests Locally
```bash
cd financial-normalizer
python run_tests.py
```

All tests must pass before submitting a PR.

---

## 📚 Documentation

### Updating Documentation
- Main docs are in root directory (*.md files)
- Code docs are in docstrings
- Update DEVELOPMENT.md if you change architecture

### Document Your Changes
```
If you add a feature → update QUICK_START.md with example
If you change architecture → update DEVELOPMENT.md
If you fix a bug → update relevant docs
If you add a test → document what it tests
```

---

## 🚫 What NOT to Do

Don't:
- ❌ Commit directly to main branch
- ❌ Skip tests - all tests must pass
- ❌ Write code without docstrings
- ❌ Change unrelated code in your PR
- ❌ Use print() instead of logging
- ❌ Ignore code style guidelines
- ❌ Break backward compatibility without discussion
- ❌ Add dependencies without justification

---

## 📋 Before Submitting Your PR

**Checklist:**
- [ ] Code runs without errors
- [ ] All tests pass (`python run_tests.py`)
- [ ] Verify with sample data
- [ ] Code follows style guidelines
- [ ] Docstrings added for new code
- [ ] Relevant documentation updated
- [ ] Commit messages are clear
- [ ] No unrelated changes included

---

## 💬 Getting Help

- Check [PROJECT_REVIEW.md](PROJECT_REVIEW.md) for technical details
- Ask questions in your PR or issues
- Review existing code for examples
- Look at test cases for usage patterns

---

## 🎉 Thank You!

Thank you for contributing to make this project better! All contributions, no matter how small, are appreciated.

````
