import os
import re

def remove_multiple_blank_lines(text):
    # This regular expression replaces multiple consecutive blank lines with a single blank line
    return re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

def process_markdown_file(file_path):
    if file_path.endswith(".md") and os.path.isfile(file_path):
        try:
            with open(file_path, 'r+', encoding='utf-8') as file:
                content = file.read()
                cleaned_content = remove_multiple_blank_lines(content)
                file.seek(0)  # Go back to the beginning of the file
                file.write(cleaned_content)
                file.truncate()  # Remove any remaining part of the original content
            print(f"Processed file: {file_path}")
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
    else:
        print(f"Skipping: {file_path} (not a markdown file or not a file)")

if __name__ == "__main__":
    file_to_process = '/Users/encord/Git/encord-docs-mint/agents-documentation/Reference/Core/Agents-Reference-Core.md'   # Change to your input file path
    
    process_markdown_file(file_to_process)