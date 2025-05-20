import re
import os

def remove_consecutive_h2(file_path):
    """Removes consecutive H2 headings with no content in between from a markdown file."""
    try:
        with open(file_path, 'r+', encoding='utf-8') as f:
            content = f.read()
            original_length = len(content)
            cleaned_content = re.sub(r'##\s+.*\n\n##\s+.*\n', '', content)
            cleaned_content = re.sub(r'##\s+.*\n##\s+.*\n', '', cleaned_content) # Run twice to catch more cases

            if len(cleaned_content) < original_length:
                f.seek(0)
                f.write(cleaned_content)
                f.truncate()
                print(f"Removed consecutive H2 headings from: {file_path}")
            else:
                print(f"No consecutive H2 headings found in: {file_path}")

    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except Exception as e:
        print(f"An error occurred while processing {file_path}: {e}")

if __name__ == "__main__":
    file_to_process = '/Users/encord/Git/encord-docs-mint/agents-documentation/Reference/Task-Agents/Agents-Reference-Task-Agents.md'  # Replace with the path to your file
    remove_consecutive_h2(file_to_process)