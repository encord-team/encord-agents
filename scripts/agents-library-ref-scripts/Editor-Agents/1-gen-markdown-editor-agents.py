import os
import subprocess
import re

# Define the base directories of your Python files and their desired H1 headings
input_folders = {
    'GCP': '/Users/encord/Git/encord-agents/encord_agents/gcp',
    'FastAPI': '/Users/encord/Git/encord-agents/encord_agents/fastapi'  # Example second input folder
}

# Define the output markdown file path
output_file = '/Users/encord/Git/encord-docs-mint/agents-documentation/Reference/Editor-Agents/Agents-Reference-Editor-Agents.md'

# Ensure the output directory exists
os.makedirs(os.path.dirname(output_file), exist_ok=True)

def adjust_headings(markdown_content, level_adjustment=1):
    """Adjusts markdown headings by a specified level."""
    lines = markdown_content.splitlines()
    adjusted_lines = []
    for line in lines:
        match = re.match(r'^(#+)\s+(.*)', line)
        if match:
            current_level = len(match.group(1))
            new_level = current_level + level_adjustment
            adjusted_lines.append('#' * min(new_level, 6) + ' ' + match.group(2))
        else:
            adjusted_lines.append(line)
    return '\n'.join(adjusted_lines)

def remove_html_anchors(markdown_content):
    """Removes all <a> tags from the markdown content."""
    return re.sub(r'<a\s+id="[^"]*"></a>', '', markdown_content)

# Open the output file in write mode
with open(output_file, 'w') as outfile:
    # Iterate over each input folder and its designated H1 heading
    for folder_name, base_dir in input_folders.items():
        outfile.write(f"# {folder_name}\n\n")
        print(f"Processing folder: {folder_name} from {base_dir}")

        # Iterate over each Python file in the input folder and its subdirectories
        for root, dirs, files in os.walk(base_dir):
            # Determine the relative path of the current directory
            relative_dir = os.path.relpath(root, base_dir)
            if relative_dir != '.':
                module_prefix = relative_dir.replace(os.sep, '.') + '.'
            else:
                module_prefix = ''

            for file in files:
                if file.endswith('.py') and file != '__init__.py':
                    # Remove the .py extension to get the module name
                    module_name = file[:-3]
                    full_module_name = f"{module_prefix}{module_name}"

                    print(f"  Generating documentation for {full_module_name}")

                    command = [
                        'pydoc-markdown',
                        '--verbose',
                        '-I', base_dir,
                        '-m', full_module_name
                    ]

                    # Run pydoc-markdown and capture the output
                    result = subprocess.run(command, capture_output=True, text=True)

                    if result.returncode == 0:
                        # Adjust headings to be H2 and below
                        adjusted_content = adjust_headings(result.stdout, level_adjustment=1)
                        # Remove HTML anchor elements
                        content_without_anchors = remove_html_anchors(adjusted_content)
                        outfile.write(content_without_anchors)
                        outfile.write("\n\n")
                    else:
                        outfile.write(f"## Error generating documentation for {module_name}:\n")
                        outfile.write(result.stderr)
                        outfile.write("\n\n")

print(f"Documentation generation complete in: {output_file}")