# Instructions Folder

Place your natural language scripts here as `.txt` files.

## Format

Each file can contain:
- Lines starting with `#` are comments (ignored)
- Each line is an instruction to execute
- Blank lines are ignored

## Example

```txt
# Login to Example Site
Go to example.com/login
Type "user@email.com" in the email field
Type "password123" in the password field
Click the Sign In button
```

## Running

```bash
llm-web-agent run-file instructions/mui_demo.txt --visible
```

## Available Scripts

| File | Description |
|------|-------------|
| `mui_demo.txt` | Navigate MUI documentation |
| `google_search.txt` | Simple Google search |
