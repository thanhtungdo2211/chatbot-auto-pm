# Example data files

This directory contains example data for testing and demonstration.

## Files

- `example_project.json` - Example project structure
- `example_tasks.csv` - Example task list
- `example_team.json` - Example team member data

## Usage

Use these files to test the project creation and management features:

```python
with open('data/examples/example_project.json', 'r') as f:
    project_data = f.read()

# Send to API
result = chat(user_id=123, file_content=project_data)
```
