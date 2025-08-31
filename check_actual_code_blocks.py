#!/usr/bin/env python3
"""Check for actual unmatched code blocks in markdown files."""


def check_code_blocks(file_path):
    """Check for actual unmatched code blocks."""
    with open(file_path, encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    in_code_block = False
    code_block_count = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('```'):
            if in_code_block:
                in_code_block = False
                print(f"Line {i}: Closing code block: {stripped}")
            else:
                in_code_block = True
                print(f"Line {i}: Opening code block: {stripped}")
            code_block_count += 1

    print(f"\nTotal code block markers: {code_block_count}")
    print(f"Code blocks balanced: {code_block_count % 2 == 0}")
    print(f"Currently in code block: {in_code_block}")

    return code_block_count % 2 == 0

if __name__ == "__main__":
    file_path = "/home/ubuntu/comet/wiki/02-core/04-error-handling.md"
    is_balanced = check_code_blocks(file_path)
    print(f"\nResult: {'BALANCED' if is_balanced else 'UNBALANCED'}")
